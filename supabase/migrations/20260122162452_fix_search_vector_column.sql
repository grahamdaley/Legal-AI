-- Fix hybrid search functions to use to_tsvector instead of non-existent search_vector column
-- The previous migration (20260122162017) referenced cc.search_vector and l.search_vector
-- which don't exist on court_cases and legislation tables

DROP FUNCTION IF EXISTS search_cases_hybrid(TEXT, VECTOR(1024), INT, FLOAT, TEXT, INT, INT);
DROP FUNCTION IF EXISTS search_legislation_hybrid(TEXT, VECTOR(1024), INT, FLOAT, TEXT);

-- =========================
-- CASES: HYBRID SEARCH (FIXED)
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
    similarity_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    ts_query tsquery;
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    PERFORM set_config('hnsw.ef_search', '100', true);
    
    ts_query := plainto_tsquery('english', query_text);
    
    RETURN QUERY
    WITH semantic_chunks AS (
        SELECT 
            ce.case_id,
            ce.chunk_index AS c_idx,
            ce.chunk_text AS c_text,
            (1 - (ce.embedding <=> query_embedding))::FLOAT AS sem_score
        FROM case_embeddings_cohere ce
        WHERE ce.embedding IS NOT NULL
          AND LENGTH(ce.chunk_text) >= 100  -- Filter out short chunks
        ORDER BY ce.embedding <=> query_embedding
        LIMIT match_count * 10
    ),
    keyword_matches AS (
        SELECT 
            cc.id AS case_id,
            ts_rank_cd(
                to_tsvector('english', COALESCE(cc.case_name, '') || ' ' || COALESCE(cc.headnote, '') || ' ' || COALESCE(cc.full_text, '')),
                ts_query
            )::FLOAT AS kw_score
        FROM court_cases cc
        WHERE to_tsvector('english', COALESCE(cc.case_name, '') || ' ' || COALESCE(cc.headnote, '') || ' ' || COALESCE(cc.full_text, ''))
              @@ ts_query
        LIMIT match_count * 10
    ),
    combined AS (
        SELECT 
            COALESCE(sc.case_id, km.case_id) AS case_id,
            sc.c_idx,
            sc.c_text,
            (
                COALESCE(sc.sem_score, 0) * semantic_weight +
                COALESCE(km.kw_score, 0) * (1 - semantic_weight)
            ) AS combined_score
        FROM semantic_chunks sc
        FULL OUTER JOIN keyword_matches km ON sc.case_id = km.case_id
    ),
    best_chunks AS (
        SELECT DISTINCT ON (c.case_id)
            c.case_id,
            c.c_idx,
            c.c_text,
            c.combined_score
        FROM combined c
        ORDER BY c.case_id, c.combined_score DESC
    )
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
        bc.combined_score AS similarity_score
    FROM best_chunks bc
    JOIN court_cases cc ON cc.id = bc.case_id
    WHERE (filter_court IS NULL OR cc.court_code = filter_court)
        AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
        AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
    ORDER BY bc.combined_score DESC, cc.decision_date DESC NULLS LAST
    LIMIT match_count;
END;
$$;

-- =========================
-- LEGISLATION: HYBRID SEARCH (FIXED)
-- =========================
CREATE OR REPLACE FUNCTION search_legislation_hybrid(
    query_text TEXT,
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 20,
    semantic_weight FLOAT DEFAULT 0.7,
    filter_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    legislation_id UUID,
    title_en TEXT,
    title_zh TEXT,
    chapter_number TEXT,
    type TEXT,
    status TEXT,
    chunk_index INT,
    chunk_text TEXT,
    similarity_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    ts_query tsquery;
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    PERFORM set_config('hnsw.ef_search', '100', true);
    
    ts_query := plainto_tsquery('english', query_text);
    
    RETURN QUERY
    WITH semantic_chunks AS (
        SELECT 
            le.legislation_id AS leg_id,
            le.chunk_index AS c_idx,
            le.chunk_text AS c_text,
            (1 - (le.embedding <=> query_embedding))::FLOAT AS sem_score
        FROM legislation_embeddings_cohere le
        WHERE le.embedding IS NOT NULL
          AND LENGTH(le.chunk_text) >= 100  -- Filter out short chunks
        ORDER BY le.embedding <=> query_embedding
        LIMIT match_count * 10
    ),
    keyword_matches AS (
        SELECT 
            l.id AS leg_id,
            ts_rank_cd(
                to_tsvector('english', COALESCE(l.title_en, '') || ' ' || COALESCE(l.title_zh, '')),
                ts_query
            )::FLOAT AS kw_score
        FROM legislation l
        WHERE to_tsvector('english', COALESCE(l.title_en, '') || ' ' || COALESCE(l.title_zh, ''))
              @@ ts_query
        LIMIT match_count * 10
    ),
    combined AS (
        SELECT 
            COALESCE(sc.leg_id, km.leg_id) AS leg_id,
            sc.c_idx,
            sc.c_text,
            (
                COALESCE(sc.sem_score, 0) * semantic_weight +
                COALESCE(km.kw_score, 0) * (1 - semantic_weight)
            ) AS combined_score
        FROM semantic_chunks sc
        FULL OUTER JOIN keyword_matches km ON sc.leg_id = km.leg_id
    ),
    best_chunks AS (
        SELECT DISTINCT ON (c.leg_id)
            c.leg_id,
            c.c_idx,
            c.c_text,
            c.combined_score
        FROM combined c
        ORDER BY c.leg_id, c.combined_score DESC
    )
    SELECT 
        bc.leg_id AS id,
        l.id AS legislation_id,
        l.title_en,
        l.title_zh,
        l.chapter_number,
        l.type,
        l.status,
        bc.c_idx AS chunk_index,
        LEFT(bc.c_text, 500) AS chunk_text,
        bc.combined_score AS similarity_score
    FROM best_chunks bc
    JOIN legislation l ON l.id = bc.leg_id
    WHERE (filter_type IS NULL OR l.type = filter_type)
    ORDER BY bc.combined_score DESC
    LIMIT match_count;
END;
$$;
