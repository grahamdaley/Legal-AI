-- Optimize search by using two-phase approach:
-- 1. Get top N*5 chunks using vector index (fast approximate search)
-- 2. Deduplicate by case/legislation ID (small result set, fast)
-- Also returns chunk_text so users can see the exact relevant passage

DROP FUNCTION IF EXISTS search_cases_semantic(VECTOR(1024), INT, TEXT, INT, INT);
DROP FUNCTION IF EXISTS search_cases_hybrid(TEXT, VECTOR(1024), INT, FLOAT, TEXT, INT, INT);
DROP FUNCTION IF EXISTS search_legislation_semantic(VECTOR(1024), INT, TEXT);
DROP FUNCTION IF EXISTS search_legislation_hybrid(TEXT, VECTOR(1024), INT, FLOAT, TEXT);

-- =========================
-- CASES: SEMANTIC SEARCH (OPTIMIZED)
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
    chunk_index INT,
    chunk_text TEXT,
    similarity_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    -- Set HNSW search parameter for faster approximate search
    PERFORM set_config('hnsw.ef_search', '100', true);
    
    RETURN QUERY
    -- Phase 1: Get top N*5 chunks using index (fast approximate search)
    WITH top_chunks AS (
        SELECT 
            ce.case_id,
            ce.chunk_index AS c_idx,
            ce.chunk_text AS c_text,
            (1 - (ce.embedding <=> query_embedding))::FLOAT AS sim_score
        FROM case_embeddings_cohere ce
        WHERE ce.embedding IS NOT NULL
        ORDER BY ce.embedding <=> query_embedding
        LIMIT match_count * 5
    ),
    -- Phase 2: Deduplicate by case_id, keeping best chunk
    best_chunks AS (
        SELECT DISTINCT ON (tc.case_id)
            tc.case_id,
            tc.c_idx,
            tc.c_text,
            tc.sim_score
        FROM top_chunks tc
        ORDER BY tc.case_id, tc.sim_score DESC
    )
    -- Join with case data and apply filters
    SELECT 
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_id,
        cc.court_code,
        cc.decision_date,
        cc.headnote,
        bc.c_idx AS chunk_index,
        LEFT(bc.c_text, 500) AS chunk_text,
        bc.sim_score AS similarity_score
    FROM best_chunks bc
    JOIN court_cases cc ON cc.id = bc.case_id
    WHERE (filter_court IS NULL OR cc.court_code = filter_court)
        AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
        AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
    ORDER BY bc.sim_score DESC, cc.decision_date DESC NULLS LAST
    LIMIT match_count;
END;
$$;

-- =========================
-- CASES: HYBRID SEARCH (OPTIMIZED)
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
    chunk_index INT,
    chunk_text TEXT,
    semantic_score FLOAT,
    fts_score FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    PERFORM set_config('hnsw.ef_search', '100', true);
    
    RETURN QUERY
    -- Phase 1: Get top chunks using vector index
    WITH top_chunks AS (
        SELECT 
            ce.case_id,
            ce.chunk_index AS c_idx,
            ce.chunk_text AS c_text,
            (1 - (ce.embedding <=> query_embedding))::FLOAT AS sim_score
        FROM case_embeddings_cohere ce
        WHERE ce.embedding IS NOT NULL
        ORDER BY ce.embedding <=> query_embedding
        LIMIT match_count * 5
    ),
    -- Phase 2: Deduplicate by case_id, keeping best chunk
    sem AS (
        SELECT DISTINCT ON (tc.case_id)
            tc.case_id,
            tc.c_idx,
            tc.c_text,
            tc.sim_score
        FROM top_chunks tc
        ORDER BY tc.case_id, tc.sim_score DESC
    ),
    -- Full-text search on cases
    fts AS (
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
        LIMIT match_count * 3
    ),
    fts_norm AS (
        SELECT 
            case_id,
            CASE WHEN MAX(fts_raw) OVER () = 0 THEN 0
                 ELSE fts_raw / NULLIF(MAX(fts_raw) OVER (), 0)
            END AS fts_score
        FROM fts
    ),
    -- Combine semantic and FTS results
    combined AS (
        SELECT 
            COALESCE(s.case_id, f.case_id) AS case_id,
            s.c_idx,
            s.c_text,
            COALESCE(s.sim_score, 0.0) AS sem_score,
            COALESCE(f.fts_score, 0.0) AS fts_score
        FROM sem s
        FULL OUTER JOIN fts_norm f ON s.case_id = f.case_id
    )
    SELECT 
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_id,
        cc.court_code,
        cc.decision_date,
        cc.headnote,
        c.c_idx AS chunk_index,
        LEFT(c.c_text, 500) AS chunk_text,
        c.sem_score::FLOAT AS semantic_score,
        c.fts_score::FLOAT AS fts_score,
        (semantic_weight * c.sem_score + (1 - semantic_weight) * c.fts_score)::FLOAT AS combined_score
    FROM combined c
    JOIN court_cases cc ON cc.id = c.case_id
    WHERE (filter_court IS NULL OR cc.court_code = filter_court)
        AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
        AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
    ORDER BY (semantic_weight * c.sem_score + (1 - semantic_weight) * c.fts_score) DESC, cc.decision_date DESC NULLS LAST
    LIMIT match_count;
END;
$$;

-- =========================
-- LEGISLATION: SEMANTIC SEARCH (OPTIMIZED)
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
    chunk_index INT,
    chunk_text TEXT,
    similarity_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    PERFORM set_config('hnsw.ef_search', '100', true);
    
    RETURN QUERY
    -- Phase 1: Get top chunks using vector index
    WITH top_chunks AS (
        SELECT 
            le.section_id AS sec_id,
            le.chunk_index AS c_idx,
            le.chunk_text AS c_text,
            (1 - (le.embedding <=> query_embedding))::FLOAT AS sim_score
        FROM legislation_embeddings_cohere le
        WHERE le.embedding IS NOT NULL
        ORDER BY le.embedding <=> query_embedding
        LIMIT match_count * 5
    ),
    -- Phase 2: Deduplicate by legislation_id, keeping best chunk
    best_chunks AS (
        SELECT DISTINCT ON (ls.legislation_id)
            tc.sec_id,
            ls.legislation_id AS leg_id,
            tc.c_idx,
            tc.c_text,
            tc.sim_score
        FROM top_chunks tc
        JOIN legislation_sections ls ON ls.id = tc.sec_id
        ORDER BY ls.legislation_id, tc.sim_score DESC
    )
    SELECT 
        bc.sec_id AS section_id,
        l.id AS legislation_id,
        l.chapter_number,
        l.title_en,
        l.title_zh,
        l.type::TEXT,
        l.status::TEXT,
        ls.section_number,
        ls.title AS section_title,
        LEFT(ls.content, 500) AS content_snippet,
        bc.c_idx AS chunk_index,
        LEFT(bc.c_text, 500) AS chunk_text,
        bc.sim_score AS similarity_score
    FROM best_chunks bc
    JOIN legislation l ON l.id = bc.leg_id
    JOIN legislation_sections ls ON ls.id = bc.sec_id
    WHERE (filter_type IS NULL OR l.type::TEXT = filter_type)
    ORDER BY bc.sim_score DESC, l.chapter_number DESC NULLS LAST
    LIMIT match_count;
END;
$$;

-- =========================
-- LEGISLATION: HYBRID SEARCH (OPTIMIZED)
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
    chunk_index INT,
    chunk_text TEXT,
    semantic_score FLOAT,
    fts_score FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    PERFORM set_config('hnsw.ef_search', '100', true);
    
    RETURN QUERY
    -- Phase 1: Get top chunks using vector index
    WITH top_chunks AS (
        SELECT 
            le.section_id AS sec_id,
            le.chunk_index AS c_idx,
            le.chunk_text AS c_text,
            (1 - (le.embedding <=> query_embedding))::FLOAT AS sim_score
        FROM legislation_embeddings_cohere le
        WHERE le.embedding IS NOT NULL
        ORDER BY le.embedding <=> query_embedding
        LIMIT match_count * 5
    ),
    -- Phase 2: Deduplicate by legislation_id, keeping best chunk
    sem AS (
        SELECT DISTINCT ON (ls.legislation_id)
            tc.sec_id,
            ls.legislation_id AS leg_id,
            tc.c_idx,
            tc.c_text,
            tc.sim_score
        FROM top_chunks tc
        JOIN legislation_sections ls ON ls.id = tc.sec_id
        ORDER BY ls.legislation_id, tc.sim_score DESC
    ),
    -- Full-text search on legislation sections
    fts AS (
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
        LIMIT match_count * 3
    ),
    fts_dedup AS (
        SELECT DISTINCT ON (leg_id)
            sec_id,
            leg_id,
            fts_raw
        FROM fts
        ORDER BY leg_id, fts_raw DESC
    ),
    fts_norm AS (
        SELECT 
            sec_id,
            leg_id,
            CASE WHEN MAX(fts_raw) OVER () = 0 THEN 0
                 ELSE fts_raw / NULLIF(MAX(fts_raw) OVER (), 0)
            END AS fts_score
        FROM fts_dedup
    ),
    -- Combine semantic and FTS results
    combined AS (
        SELECT 
            COALESCE(s.sec_id, f.sec_id) AS sec_id,
            COALESCE(s.leg_id, f.leg_id) AS leg_id,
            s.c_idx,
            s.c_text,
            COALESCE(s.sim_score, 0.0) AS sem_score,
            COALESCE(f.fts_score, 0.0) AS fts_score
        FROM sem s
        FULL OUTER JOIN fts_norm f ON s.leg_id = f.leg_id
    )
    SELECT 
        c.sec_id AS section_id,
        l.id AS legislation_id,
        l.chapter_number,
        l.title_en,
        l.title_zh,
        l.type::TEXT,
        l.status::TEXT,
        ls.section_number,
        ls.title AS section_title,
        LEFT(ls.content, 500) AS content_snippet,
        c.c_idx AS chunk_index,
        LEFT(c.c_text, 500) AS chunk_text,
        c.sem_score::FLOAT AS semantic_score,
        c.fts_score::FLOAT AS fts_score,
        (semantic_weight * c.sem_score + (1 - semantic_weight) * c.fts_score)::FLOAT AS combined_score
    FROM combined c
    JOIN legislation l ON l.id = c.leg_id
    JOIN legislation_sections ls ON ls.id = c.sec_id
    ORDER BY (semantic_weight * c.sem_score + (1 - semantic_weight) * c.fts_score) DESC, l.chapter_number DESC NULLS LAST
    LIMIT match_count;
END;
$$;
