-- Fix legislation search functions to return type and status fields
-- These fields are required by the frontend LegislationResult type

-- Must DROP functions first because we're changing the return type
DROP FUNCTION IF EXISTS search_legislation_semantic(VECTOR(1024), INT, TEXT);
DROP FUNCTION IF EXISTS search_legislation_hybrid(TEXT, VECTOR(1024), INT, FLOAT, TEXT);

-- =========================
-- LEGISLATION: SEMANTIC SEARCH
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
        (1 - (le.embedding <=> query_embedding))::FLOAT AS similarity_score
    FROM legislation_embeddings_cohere le
    JOIN legislation_sections ls ON ls.id = le.section_id
    JOIN legislation l ON l.id = ls.legislation_id
    WHERE le.embedding IS NOT NULL
        AND le.chunk_index = 0
        AND (filter_type IS NULL OR l.type::TEXT = filter_type)
    ORDER BY le.embedding <=> query_embedding, l.chapter_number DESC NULLS LAST
    LIMIT match_count;
END;
$$;

-- =========================
-- LEGISLATION: HYBRID SEARCH
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
      SELECT 
        le.section_id AS sec_id,
        (1 - (le.embedding <=> query_embedding))::FLOAT AS sem_score
      FROM legislation_embeddings_cohere le
      JOIN legislation_sections ls ON ls.id = le.section_id
      JOIN legislation l ON l.id = ls.legislation_id
      WHERE le.embedding IS NOT NULL
        AND le.chunk_index = 0
        AND (filter_type IS NULL OR l.type::TEXT = filter_type)
      ORDER BY le.embedding <=> query_embedding
      LIMIT GREATEST(match_count * 3, 100)
    ), fts AS (
      SELECT 
        ls.id AS sec_id,
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
    ), fts_norm AS (
      SELECT 
        sec_id,
        CASE WHEN MAX(fts_raw) OVER () = 0 THEN 0
             ELSE fts_raw / NULLIF(MAX(fts_raw) OVER (), 0)
        END AS fts_score
      FROM fts
    )
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
      COALESCE(s.sem_score, 0.0)::FLOAT AS semantic_score,
      COALESCE(f.fts_score, 0.0)::FLOAT AS fts_score,
      (semantic_weight * COALESCE(s.sem_score, 0.0) + (1 - semantic_weight) * COALESCE(f.fts_score, 0.0))::FLOAT AS combined_score
    FROM legislation_sections ls
    JOIN legislation l ON l.id = ls.legislation_id
    LEFT JOIN sem s ON s.sec_id = ls.id
    LEFT JOIN fts_norm f ON f.sec_id = ls.id
    WHERE s.sec_id IS NOT NULL OR f.sec_id IS NOT NULL
    ORDER BY (semantic_weight * COALESCE(s.sem_score, 0.0) + (1 - semantic_weight) * COALESCE(f.fts_score, 0.0)) DESC, l.chapter_number DESC NULLS LAST
    LIMIT match_count;
END;
$$;
