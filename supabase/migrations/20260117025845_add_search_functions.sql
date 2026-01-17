-- Search Functions for Legal AI
-- Implements semantic and hybrid search for cases and legislation

-- =============================================================================
-- CASE SEARCH FUNCTIONS
-- =============================================================================

-- Semantic search for court cases using vector similarity
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
    RETURN QUERY
    SELECT 
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_id,
        cc.court_code,
        cc.decision_date,
        cc.headnote,
        1 - (ce.embedding <=> query_embedding) AS similarity_score
    FROM case_embeddings_cohere ce
    JOIN court_cases cc ON cc.id = ce.case_id
    WHERE 
        ce.embedding IS NOT NULL
        AND ce.chunk_index = 0  -- Use first chunk for document-level search
        AND (filter_court IS NULL OR cc.court_code = filter_court)
        AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
        AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
    ORDER BY ce.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Hybrid search combining semantic and full-text search
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
DECLARE
    max_fts_score FLOAT;
BEGIN
    -- Create temp table for semantic results
    CREATE TEMP TABLE IF NOT EXISTS temp_semantic_results AS
    SELECT 
        cc.id AS case_id,
        1 - (ce.embedding <=> query_embedding) AS sem_score
    FROM case_embeddings_cohere ce
    JOIN court_cases cc ON cc.id = ce.case_id
    WHERE 
        ce.embedding IS NOT NULL
        AND ce.chunk_index = 0
        AND (filter_court IS NULL OR cc.court_code = filter_court)
        AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
        AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
    ORDER BY ce.embedding <=> query_embedding
    LIMIT match_count * 3;  -- Get more candidates for reranking

    -- Create temp table for FTS results
    CREATE TEMP TABLE IF NOT EXISTS temp_fts_results AS
    SELECT 
        cc.id AS case_id,
        ts_rank_cd(
            to_tsvector('english', COALESCE(cc.case_name, '') || ' ' || COALESCE(cc.headnote, '') || ' ' || COALESCE(cc.full_text, '')),
            plainto_tsquery('english', query_text)
        ) AS fts_raw_score
    FROM court_cases cc
    WHERE 
        to_tsvector('english', COALESCE(cc.case_name, '') || ' ' || COALESCE(cc.headnote, '') || ' ' || COALESCE(cc.full_text, '')) 
        @@ plainto_tsquery('english', query_text)
        AND (filter_court IS NULL OR cc.court_code = filter_court)
        AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
        AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to);

    -- Get max FTS score for normalization
    SELECT COALESCE(MAX(fts_raw_score), 1.0) INTO max_fts_score FROM temp_fts_results;
    IF max_fts_score = 0 THEN max_fts_score := 1.0; END IF;

    -- Combine results
    RETURN QUERY
    SELECT 
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_id,
        cc.court_code,
        cc.decision_date,
        cc.headnote,
        COALESCE(sr.sem_score, 0.0)::FLOAT AS semantic_score,
        COALESCE(fr.fts_raw_score / max_fts_score, 0.0)::FLOAT AS fts_score,
        (
            semantic_weight * COALESCE(sr.sem_score, 0.0) + 
            (1 - semantic_weight) * COALESCE(fr.fts_raw_score / max_fts_score, 0.0)
        )::FLOAT AS combined_score
    FROM court_cases cc
    LEFT JOIN temp_semantic_results sr ON sr.case_id = cc.id
    LEFT JOIN temp_fts_results fr ON fr.case_id = cc.id
    WHERE sr.case_id IS NOT NULL OR fr.case_id IS NOT NULL
    ORDER BY (
        semantic_weight * COALESCE(sr.sem_score, 0.0) + 
        (1 - semantic_weight) * COALESCE(fr.fts_raw_score / max_fts_score, 0.0)
    ) DESC
    LIMIT match_count;

    -- Cleanup
    DROP TABLE IF EXISTS temp_semantic_results;
    DROP TABLE IF EXISTS temp_fts_results;
END;
$$;

-- =============================================================================
-- LEGISLATION SEARCH FUNCTIONS
-- =============================================================================

-- Semantic search for legislation sections
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
    section_number TEXT,
    section_title TEXT,
    content_snippet TEXT,
    similarity_score FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ls.id AS section_id,
        l.id AS legislation_id,
        l.chapter_number,
        l.title_en,
        ls.section_number,
        ls.title AS section_title,
        LEFT(ls.content, 500) AS content_snippet,
        1 - (le.embedding <=> query_embedding) AS similarity_score
    FROM legislation_embeddings_cohere le
    JOIN legislation_sections ls ON ls.id = le.section_id
    JOIN legislation l ON l.id = ls.legislation_id
    WHERE 
        le.embedding IS NOT NULL
        AND le.chunk_index = 0
        AND (filter_type IS NULL OR l.type::TEXT = filter_type)
    ORDER BY le.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Hybrid search for legislation
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
DECLARE
    max_fts_score FLOAT;
BEGIN
    -- Create temp table for semantic results
    CREATE TEMP TABLE IF NOT EXISTS temp_leg_semantic AS
    SELECT 
        ls.id AS sec_id,
        1 - (le.embedding <=> query_embedding) AS sem_score
    FROM legislation_embeddings_cohere le
    JOIN legislation_sections ls ON ls.id = le.section_id
    JOIN legislation l ON l.id = ls.legislation_id
    WHERE 
        le.embedding IS NOT NULL
        AND le.chunk_index = 0
        AND (filter_type IS NULL OR l.type::TEXT = filter_type)
    ORDER BY le.embedding <=> query_embedding
    LIMIT match_count * 3;

    -- Create temp table for FTS results
    CREATE TEMP TABLE IF NOT EXISTS temp_leg_fts AS
    SELECT 
        ls.id AS sec_id,
        ts_rank_cd(
            to_tsvector('english', COALESCE(ls.title, '') || ' ' || COALESCE(ls.content, '')),
            plainto_tsquery('english', query_text)
        ) AS fts_raw_score
    FROM legislation_sections ls
    JOIN legislation l ON l.id = ls.legislation_id
    WHERE 
        to_tsvector('english', COALESCE(ls.title, '') || ' ' || COALESCE(ls.content, '')) 
        @@ plainto_tsquery('english', query_text)
        AND (filter_type IS NULL OR l.type::TEXT = filter_type);

    -- Get max FTS score for normalization
    SELECT COALESCE(MAX(fts_raw_score), 1.0) INTO max_fts_score FROM temp_leg_fts;
    IF max_fts_score = 0 THEN max_fts_score := 1.0; END IF;

    -- Combine results
    RETURN QUERY
    SELECT 
        ls.id AS section_id,
        l.id AS legislation_id,
        l.chapter_number,
        l.title_en,
        ls.section_number,
        ls.title AS section_title,
        LEFT(ls.content, 500) AS content_snippet,
        COALESCE(sr.sem_score, 0.0)::FLOAT AS semantic_score,
        COALESCE(fr.fts_raw_score / max_fts_score, 0.0)::FLOAT AS fts_score,
        (
            semantic_weight * COALESCE(sr.sem_score, 0.0) + 
            (1 - semantic_weight) * COALESCE(fr.fts_raw_score / max_fts_score, 0.0)
        )::FLOAT AS combined_score
    FROM legislation_sections ls
    JOIN legislation l ON l.id = ls.legislation_id
    LEFT JOIN temp_leg_semantic sr ON sr.sec_id = ls.id
    LEFT JOIN temp_leg_fts fr ON fr.sec_id = ls.id
    WHERE sr.sec_id IS NOT NULL OR fr.sec_id IS NOT NULL
    ORDER BY (
        semantic_weight * COALESCE(sr.sem_score, 0.0) + 
        (1 - semantic_weight) * COALESCE(fr.fts_raw_score / max_fts_score, 0.0)
    ) DESC
    LIMIT match_count;

    -- Cleanup
    DROP TABLE IF EXISTS temp_leg_semantic;
    DROP TABLE IF EXISTS temp_leg_fts;
END;
$$;

-- =============================================================================
-- ADDITIONAL INDEXES FOR SEARCH PERFORMANCE
-- =============================================================================

-- HNSW index for case embeddings (faster than ivfflat for smaller datasets)
CREATE INDEX IF NOT EXISTS idx_case_embeddings_cohere_hnsw 
    ON case_embeddings_cohere 
    USING hnsw (embedding vector_cosine_ops);

-- HNSW index for legislation embeddings
CREATE INDEX IF NOT EXISTS idx_legislation_embeddings_cohere_hnsw 
    ON legislation_embeddings_cohere 
    USING hnsw (embedding vector_cosine_ops);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON FUNCTION search_cases_semantic IS 'Semantic search for court cases using vector similarity on embeddings';
COMMENT ON FUNCTION search_cases_hybrid IS 'Hybrid search combining semantic similarity and full-text search for court cases';
COMMENT ON FUNCTION search_legislation_semantic IS 'Semantic search for legislation sections using vector similarity';
COMMENT ON FUNCTION search_legislation_hybrid IS 'Hybrid search combining semantic and full-text search for legislation';