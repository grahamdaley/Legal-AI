-- Optimize search functions to prevent statement timeout
-- Use DISTINCT ON instead of MIN() GROUP BY for better performance

-- =========================
-- CASES: SEMANTIC SEARCH
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
LANGUAGE sql
STABLE
AS $$
WITH nn AS (
  SELECT DISTINCT ON (ce.case_id) 
         ce.case_id,
         (ce.embedding <=> query_embedding) AS distance
  FROM case_embeddings_cohere ce
  JOIN court_cases cc ON cc.id = ce.case_id
  WHERE ce.embedding IS NOT NULL
    AND (filter_court IS NULL OR cc.court_code = filter_court)
    AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
    AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
  ORDER BY ce.case_id, ce.embedding <=> query_embedding
)
SELECT 
  cc.id,
  cc.neutral_citation,
  cc.case_name,
  cc.court_id,
  cc.court_code,
  cc.decision_date,
  cc.headnote,
  (1 - nn.distance)::FLOAT AS similarity_score
FROM nn
JOIN court_cases cc ON cc.id = nn.case_id
ORDER BY nn.distance
LIMIT match_count;
$$;

-- =========================
-- CASES: HYBRID SEARCH
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
LANGUAGE sql
STABLE
AS $$
WITH sem AS (
  SELECT DISTINCT ON (ce.case_id)
         ce.case_id,
         (ce.embedding <=> query_embedding) AS min_dist
  FROM case_embeddings_cohere ce
  JOIN court_cases cc ON cc.id = ce.case_id
  WHERE ce.embedding IS NOT NULL
    AND (filter_court IS NULL OR cc.court_code = filter_court)
    AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
    AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
  ORDER BY ce.case_id, ce.embedding <=> query_embedding
  LIMIT GREATEST(match_count * 50, 500)
), fts AS (
  SELECT cc.id AS case_id,
         ts_rank_cd(
           to_tsvector('english', COALESCE(cc.case_name, '') || ' ' || COALESCE(cc.headnote, '') || ' ' || COALESCE(cc.full_text, '')),
           plainto_tsquery('english', query_text)
         ) AS fts_raw
  FROM court_cases cc
  WHERE (filter_court IS NULL OR cc.court_code = filter_court)
    AND (filter_year_from IS NULL OR EXTRACT(YEAR FROM cc.decision_date) >= filter_year_from)
    AND (filter_year_to IS NULL OR EXTRACT(YEAR FROM cc.decision_date) <= filter_year_to)
), fts_norm AS (
  SELECT case_id,
         CASE WHEN MAX(fts_raw) OVER () = 0 THEN 0
              ELSE fts_raw / NULLIF(MAX(fts_raw) OVER (), 0)
         END AS fts_score
  FROM fts
), joined AS (
  SELECT cc.id,
         cc.neutral_citation,
         cc.case_name,
         cc.court_id,
         cc.court_code,
         cc.decision_date,
         cc.headnote,
         (1 - COALESCE(st.min_dist, 1.0))::FLOAT AS semantic_score,
         COALESCE(fn.fts_score, 0.0)::FLOAT AS fts_score
  FROM court_cases cc
  LEFT JOIN sem st ON st.case_id = cc.id
  LEFT JOIN fts_norm fn ON fn.case_id = cc.id
  WHERE st.case_id IS NOT NULL OR fn.case_id IS NOT NULL
)
SELECT 
  id,
  neutral_citation,
  case_name,
  court_id,
  court_code,
  decision_date,
  headnote,
  semantic_score,
  fts_score,
  (semantic_weight * semantic_score + (1 - semantic_weight) * fts_score)::FLOAT AS combined_score
FROM joined
ORDER BY (semantic_weight * semantic_score + (1 - semantic_weight) * fts_score) DESC
LIMIT match_count;
$$;

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
    section_number TEXT,
    section_title TEXT,
    content_snippet TEXT,
    similarity_score FLOAT
)
LANGUAGE sql
STABLE
AS $$
WITH nn AS (
  SELECT DISTINCT ON (le.section_id)
         le.section_id,
         (le.embedding <=> query_embedding) AS distance
  FROM legislation_embeddings_cohere le
  JOIN legislation_sections ls ON ls.id = le.section_id
  JOIN legislation l ON l.id = ls.legislation_id
  WHERE le.embedding IS NOT NULL
    AND (filter_type IS NULL OR l.type::TEXT = filter_type)
  ORDER BY le.section_id, le.embedding <=> query_embedding
)
SELECT 
  ls.id AS section_id,
  l.id AS legislation_id,
  l.chapter_number,
  l.title_en,
  ls.section_number,
  ls.title AS section_title,
  LEFT(ls.content, 500) AS content_snippet,
  (1 - nn.distance)::FLOAT AS similarity_score
FROM nn
JOIN legislation_sections ls ON ls.id = nn.section_id
JOIN legislation l ON l.id = ls.legislation_id
ORDER BY nn.distance
LIMIT match_count;
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
    section_number TEXT,
    section_title TEXT,
    content_snippet TEXT,
    semantic_score FLOAT,
    fts_score FLOAT,
    combined_score FLOAT
)
LANGUAGE sql
STABLE
AS $$
WITH sem AS (
  SELECT DISTINCT ON (le.section_id)
         le.section_id,
         (le.embedding <=> query_embedding) AS min_dist
  FROM legislation_embeddings_cohere le
  JOIN legislation_sections ls ON ls.id = le.section_id
  JOIN legislation l ON l.id = ls.legislation_id
  WHERE le.embedding IS NOT NULL
    AND (filter_type IS NULL OR l.type::TEXT = filter_type)
  ORDER BY le.section_id, le.embedding <=> query_embedding
  LIMIT GREATEST(match_count * 50, 500)
), fts AS (
  SELECT ls.id AS section_id,
         ts_rank_cd(
           to_tsvector('english', COALESCE(ls.title, '') || ' ' || COALESCE(ls.content, '')),
           plainto_tsquery('english', query_text)
         ) AS fts_raw
  FROM legislation_sections ls
  JOIN legislation l ON l.id = ls.legislation_id
  WHERE (filter_type IS NULL OR l.type::TEXT = filter_type)
), fts_norm AS (
  SELECT section_id,
         CASE WHEN MAX(fts_raw) OVER () = 0 THEN 0
              ELSE fts_raw / NULLIF(MAX(fts_raw) OVER (), 0)
         END AS fts_score
  FROM fts
), joined AS (
  SELECT 
    ls.id AS section_id,
    l.id AS legislation_id,
    l.chapter_number,
    l.title_en,
    ls.section_number,
    ls.title AS section_title,
    LEFT(ls.content, 500) AS content_snippet,
    (1 - COALESCE(st.min_dist, 1.0))::FLOAT AS semantic_score,
    COALESCE(fn.fts_score, 0.0)::FLOAT AS fts_score
  FROM legislation_sections ls
  JOIN legislation l ON l.id = ls.legislation_id
  LEFT JOIN sem st ON st.section_id = ls.id
  LEFT JOIN fts_norm fn ON fn.section_id = ls.id
  WHERE st.section_id IS NOT NULL OR fn.section_id IS NOT NULL
)
SELECT 
  section_id,
  legislation_id,
  chapter_number,
  title_en,
  section_number,
  section_title,
  content_snippet,
  semantic_score,
  fts_score,
  (semantic_weight * semantic_score + (1 - semantic_weight) * fts_score)::FLOAT AS combined_score
FROM joined
ORDER BY (semantic_weight * semantic_score + (1 - semantic_weight) * fts_score) DESC
LIMIT match_count;
$$;
