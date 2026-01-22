-- Search all chunks instead of just chunk_index = 0
-- Returns the best matching chunk per case/legislation with deduplication handled in the query

-- Must DROP functions first because we're changing the implementation significantly
DROP FUNCTION IF EXISTS search_cases_semantic(VECTOR(1024), INT, TEXT, INT, INT);
DROP FUNCTION IF EXISTS search_cases_hybrid(TEXT, VECTOR(1024), INT, FLOAT, TEXT, INT, INT);
DROP FUNCTION IF EXISTS search_legislation_semantic(VECTOR(1024), INT, TEXT);
DROP FUNCTION IF EXISTS search_legislation_hybrid(TEXT, VECTOR(1024), INT, FLOAT, TEXT);

-- =========================
-- CASES: SEMANTIC SEARCH (ALL CHUNKS)
-- =========================
CREATE OR REPLACE FUNCTION search_cases_semantic(
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 20,
    filter_court TEXT DEFAULT NULL,
    filter_year_from INT DEFAULT NULL,
    filter_year_to INT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    neutral_citation TEXT,
    case_name TEXT,
    court_id UUID,
    court_code TEXT,
    decision_date DATE,
    headnote TEXT,
    similarity_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    
    RETURN QUERY
    WITH ranked_chunks AS (
        SELECT 
            cc.id,
            cc.neutral_citation,
            cc.case_name,
            cc.court_id,
            cc.court_code,
            cc.decision_date,
            cc.headnote,
            (1 - (ce.embedding <=> query_embedding))::FLOAT AS similarity_score,
            ROW_NUMBER() OVER (PARTITION BY cc.id ORDER BY ce.embedding <=> query_embedding) AS rn
        FROM case_embeddings_cohere ce
        JOIN court_cases cc ON cc.id = ce.case_id
        WHERE ce.embedding IS NOT NULL
            AND (filter_court IS NULL OR cc.court_code = filter_court)
            AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
            AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
    )
    SELECT 
        rc.id,
        rc.neutral_citation,
        rc.case_name,
        rc.court_id,
        rc.court_code,
        rc.decision_date,
        rc.headnote,
        rc.similarity_score
    FROM ranked_chunks rc
    WHERE rc.rn = 1
    ORDER BY rc.similarity_score DESC, rc.decision_date DESC NULLS LAST
    LIMIT match_count;
END;
$$;

-- =========================
-- CASES: HYBRID SEARCH (ALL CHUNKS)
-- =========================
CREATE OR REPLACE FUNCTION search_cases_hybrid(
    query_text TEXT,
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 20,
    semantic_weight FLOAT DEFAULT 0.7,
    filter_court TEXT DEFAULT NULL,
    filter_year_from INT DEFAULT NULL,
    filter_year_to INT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    neutral_citation TEXT,
    case_name TEXT,
    court_id UUID,
    court_code TEXT,
    decision_date DATE,
    headnote TEXT,
    semantic_score FLOAT,
    fts_score FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    
    RETURN QUERY
    WITH sem AS (
      -- Get best matching chunk per case
      SELECT DISTINCT ON (ce.case_id)
        ce.case_id,
        (1 - (ce.embedding <=> query_embedding))::FLOAT AS sem_score
      FROM case_embeddings_cohere ce
      JOIN court_cases cc ON cc.id = ce.case_id
      WHERE ce.embedding IS NOT NULL
        AND (filter_court IS NULL OR cc.court_code = filter_court)
        AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
        AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
      ORDER BY ce.case_id, ce.embedding <=> query_embedding
    ), sem_top AS (
      SELECT * FROM sem
      ORDER BY sem_score DESC
      LIMIT GREATEST(match_count * 3, 100)
    ), fts AS (
      SELECT 
        cc.id AS case_id,
        ts_rank_cd(
          to_tsvector('english', COALESCE(cc.case_name, '') || ' ' || COALESCE(cc.headnote, '') || ' ' || COALESCE(cc.full_text, '')),
          plainto_tsquery('english', query_text)
        ) AS fts_raw
      FROM court_cases cc
      WHERE to_tsvector('english', COALESCE(cc.case_name, '') || ' ' || COALESCE(cc.headnote, '') || ' ' || COALESCE(cc.full_text, ''))
            @@ plainto_tsquery('english', query_text)
        AND (filter_court IS NULL OR cc.court_code = filter_court)
        AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
        AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
      LIMIT GREATEST(match_count * 3, 100)
    ), fts_norm AS (
      SELECT 
        case_id,
        CASE WHEN MAX(fts_raw) OVER () = 0 THEN 0
             ELSE fts_raw / NULLIF(MAX(fts_raw) OVER (), 0)
        END AS fts_score
      FROM fts
    )
    SELECT 
      cc.id,
      cc.neutral_citation,
      cc.case_name,
      cc.court_id,
      cc.court_code,
      cc.decision_date,
      cc.headnote,
      COALESCE(s.sem_score, 0.0)::FLOAT AS semantic_score,
      COALESCE(f.fts_score, 0.0)::FLOAT AS fts_score,
      (semantic_weight * COALESCE(s.sem_score, 0.0) + (1 - semantic_weight) * COALESCE(f.fts_score, 0.0))::FLOAT AS combined_score
    FROM court_cases cc
    LEFT JOIN sem_top s ON s.case_id = cc.id
    LEFT JOIN fts_norm f ON f.case_id = cc.id
    WHERE s.case_id IS NOT NULL OR f.case_id IS NOT NULL
    ORDER BY (semantic_weight * COALESCE(s.sem_score, 0.0) + (1 - semantic_weight) * COALESCE(f.fts_score, 0.0)) DESC, cc.decision_date DESC NULLS LAST
    LIMIT match_count;
END;
$$;

-- =========================
-- LEGISLATION: SEMANTIC SEARCH (ALL CHUNKS)
-- =========================
CREATE OR REPLACE FUNCTION search_legislation_semantic(
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 20,
    filter_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    section_id UUID,
    legislation_id UUID,
    chapter_number TEXT,
    title_en TEXT,
    title_zh TEXT,
    type TEXT,
    status TEXT,
    section_number TEXT,
    section_title TEXT,
    content_snippet TEXT,
    similarity_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    
    RETURN QUERY
    WITH ranked_chunks AS (
        SELECT 
            ls.id AS section_id,
            l.id AS legislation_id,
            l.chapter_number,
            l.title_en,
            l.title_zh,
            l.type::TEXT AS type,
            l.status::TEXT AS status,
            ls.section_number,
            ls.title AS section_title,
            LEFT(ls.content, 500) AS content_snippet,
            (1 - (le.embedding <=> query_embedding))::FLOAT AS similarity_score,
            ROW_NUMBER() OVER (PARTITION BY l.id ORDER BY le.embedding <=> query_embedding) AS rn
        FROM legislation_embeddings_cohere le
        JOIN legislation_sections ls ON ls.id = le.section_id
        JOIN legislation l ON l.id = ls.legislation_id
        WHERE le.embedding IS NOT NULL
            AND (filter_type IS NULL OR l.type::TEXT = filter_type)
    )
    SELECT 
        rc.section_id,
        rc.legislation_id,
        rc.chapter_number,
        rc.title_en,
        rc.title_zh,
        rc.type,
        rc.status,
        rc.section_number,
        rc.section_title,
        rc.content_snippet,
        rc.similarity_score
    FROM ranked_chunks rc
    WHERE rc.rn = 1
    ORDER BY rc.similarity_score DESC, rc.chapter_number DESC NULLS LAST
    LIMIT match_count;
END;
$$;

-- =========================
-- LEGISLATION: HYBRID SEARCH (ALL CHUNKS)
-- =========================
CREATE OR REPLACE FUNCTION search_legislation_hybrid(
    query_text TEXT,
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 20,
    semantic_weight FLOAT DEFAULT 0.7,
    filter_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    section_id UUID,
    legislation_id UUID,
    chapter_number TEXT,
    title_en TEXT,
    title_zh TEXT,
    type TEXT,
    status TEXT,
    section_number TEXT,
    section_title TEXT,
    content_snippet TEXT,
    semantic_score FLOAT,
    fts_score FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    
    RETURN QUERY
    WITH sem AS (
      -- Get best matching chunk per legislation
      SELECT DISTINCT ON (l.id)
        ls.id AS sec_id,
        l.id AS leg_id,
        (1 - (le.embedding <=> query_embedding))::FLOAT AS sem_score
      FROM legislation_embeddings_cohere le
      JOIN legislation_sections ls ON ls.id = le.section_id
      JOIN legislation l ON l.id = ls.legislation_id
      WHERE le.embedding IS NOT NULL
        AND (filter_type IS NULL OR l.type::TEXT = filter_type)
      ORDER BY l.id, le.embedding <=> query_embedding
    ), sem_top AS (
      SELECT * FROM sem
      ORDER BY sem_score DESC
      LIMIT GREATEST(match_count * 3, 100)
    ), fts AS (
      SELECT 
        ls.id AS sec_id,
        l.id AS leg_id,
        ts_rank_cd(
          to_tsvector('english', COALESCE(ls.title, '') || ' ' || COALESCE(ls.content, '')),
          plainto_tsquery('english', query_text)
        ) AS fts_raw
      FROM legislation_sections ls
      JOIN legislation l ON l.id = ls.legislation_id
      WHERE to_tsvector('english', COALESCE(ls.title, '') || ' ' || COALESCE(ls.content, ''))
            @@ plainto_tsquery('english', query_text)
        AND (filter_type IS NULL OR l.type::TEXT = filter_type)
      LIMIT GREATEST(match_count * 3, 100)
    ), fts_dedup AS (
      -- Deduplicate FTS results by legislation_id, keeping best score
      SELECT DISTINCT ON (leg_id)
        sec_id,
        leg_id,
        fts_raw
      FROM fts
      ORDER BY leg_id, fts_raw DESC
    ), fts_norm AS (
      SELECT 
        sec_id,
        leg_id,
        CASE WHEN MAX(fts_raw) OVER () = 0 THEN 0
             ELSE fts_raw / NULLIF(MAX(fts_raw) OVER (), 0)
        END AS fts_score
      FROM fts_dedup
    )
    SELECT 
      COALESCE(s.sec_id, f.sec_id) AS section_id,
      l.id AS legislation_id,
      l.chapter_number,
      l.title_en,
      l.title_zh,
      l.type::TEXT AS type,
      l.status::TEXT AS status,
      ls.section_number,
      ls.title AS section_title,
      LEFT(ls.content, 500) AS content_snippet,
      COALESCE(s.sem_score, 0.0)::FLOAT AS semantic_score,
      COALESCE(f.fts_score, 0.0)::FLOAT AS fts_score,
      (semantic_weight * COALESCE(s.sem_score, 0.0) + (1 - semantic_weight) * COALESCE(f.fts_score, 0.0))::FLOAT AS combined_score
    FROM sem_top s
    FULL OUTER JOIN fts_norm f ON s.leg_id = f.leg_id
    JOIN legislation l ON l.id = COALESCE(s.leg_id, f.leg_id)
    JOIN legislation_sections ls ON ls.id = COALESCE(s.sec_id, f.sec_id)
    ORDER BY (semantic_weight * COALESCE(s.sem_score, 0.0) + (1 - semantic_weight) * COALESCE(f.fts_score, 0.0)) DESC, l.chapter_number DESC NULLS LAST
    LIMIT match_count;
END;
$$;
