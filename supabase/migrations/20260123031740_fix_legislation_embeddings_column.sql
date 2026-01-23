-- Fix legislation search functions to use correct column name
-- The legislation_embeddings_cohere table has section_id (not legislation_id)
-- We need to join through legislation_sections to get to legislation

DROP FUNCTION IF EXISTS search_legislation_semantic(VECTOR(1024), INT, TEXT);
DROP FUNCTION IF EXISTS search_legislation_hybrid(TEXT, VECTOR(1024), INT, FLOAT, TEXT);

-- =========================
-- LEGISLATION: SEMANTIC SEARCH (FIXED)
-- =========================
CREATE OR REPLACE FUNCTION search_legislation_semantic(
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 20,
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
BEGIN
    PERFORM set_config('statement_timeout', '60s', true);
    PERFORM set_config('hnsw.ef_search', '100', true);
    
    RETURN QUERY
    WITH top_chunks AS (
        SELECT 
            ls.legislation_id AS leg_id,
            le.chunk_index AS c_idx,
            le.chunk_text AS c_text,
            (1 - (le.embedding <=> query_embedding))::FLOAT AS sim_score
        FROM legislation_embeddings_cohere le
        JOIN legislation_sections ls ON ls.id = le.section_id
        WHERE le.embedding IS NOT NULL
          AND LENGTH(le.chunk_text) >= 100
        ORDER BY le.embedding <=> query_embedding
        LIMIT match_count * 5
    ),
    best_chunks AS (
        SELECT DISTINCT ON (tc.leg_id)
            tc.leg_id,
            tc.c_idx,
            tc.c_text,
            tc.sim_score
        FROM top_chunks tc
        ORDER BY tc.leg_id, tc.sim_score DESC
    )
    SELECT 
        bc.leg_id AS id,
        l.id AS legislation_id,
        l.title_en,
        l.title_zh,
        l.chapter_number,
        l.type::TEXT,
        l.status::TEXT,
        bc.c_idx AS chunk_index,
        LEFT(bc.c_text, 500) AS chunk_text,
        bc.sim_score AS similarity_score
    FROM best_chunks bc
    JOIN legislation l ON l.id = bc.leg_id
    WHERE (filter_type IS NULL OR l.type::TEXT = filter_type)
    ORDER BY bc.sim_score DESC
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
            ls.legislation_id AS leg_id,
            le.chunk_index AS c_idx,
            le.chunk_text AS c_text,
            (1 - (le.embedding <=> query_embedding))::FLOAT AS sem_score
        FROM legislation_embeddings_cohere le
        JOIN legislation_sections ls ON ls.id = le.section_id
        WHERE le.embedding IS NOT NULL
          AND LENGTH(le.chunk_text) >= 100
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
        l.type::TEXT,
        l.status::TEXT,
        bc.c_idx AS chunk_index,
        LEFT(bc.c_text, 500) AS chunk_text,
        bc.combined_score AS similarity_score
    FROM best_chunks bc
    JOIN legislation l ON l.id = bc.leg_id
    WHERE (filter_type IS NULL OR l.type::TEXT = filter_type)
    ORDER BY bc.combined_score DESC
    LIMIT match_count;
END;
$$;
