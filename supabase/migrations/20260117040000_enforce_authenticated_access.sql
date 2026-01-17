-- Enforce Authenticated Access
-- This migration ensures all tables require authentication for access
-- Only registration and login are available to unauthenticated users

-- =============================================================================
-- ENABLE RLS ON EMBEDDING TABLES
-- =============================================================================

ALTER TABLE case_embeddings_cohere ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_embeddings_openai ENABLE ROW LEVEL SECURITY;
ALTER TABLE legislation_embeddings_cohere ENABLE ROW LEVEL SECURITY;
ALTER TABLE legislation_embeddings_openai ENABLE ROW LEVEL SECURITY;
ALTER TABLE headnote_corpus ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- DROP EXISTING PUBLIC READ POLICIES
-- =============================================================================

DROP POLICY IF EXISTS "Public read access for courts" ON courts;
DROP POLICY IF EXISTS "Public read access for court_cases" ON court_cases;
DROP POLICY IF EXISTS "Public read access for legislation" ON legislation;
DROP POLICY IF EXISTS "Public read access for legislation_sections" ON legislation_sections;
DROP POLICY IF EXISTS "Public read access for legislation_schedules" ON legislation_schedules;

-- =============================================================================
-- CREATE AUTHENTICATED READ POLICIES FOR LEGAL DOCUMENTS
-- =============================================================================

-- Courts: authenticated users can read
CREATE POLICY "Authenticated read access for courts" ON courts
    FOR SELECT 
    TO authenticated
    USING (true);

-- Court cases: authenticated users can read
CREATE POLICY "Authenticated read access for court_cases" ON court_cases
    FOR SELECT 
    TO authenticated
    USING (true);

-- Legislation: authenticated users can read
CREATE POLICY "Authenticated read access for legislation" ON legislation
    FOR SELECT 
    TO authenticated
    USING (true);

-- Legislation sections: authenticated users can read
CREATE POLICY "Authenticated read access for legislation_sections" ON legislation_sections
    FOR SELECT 
    TO authenticated
    USING (true);

-- Legislation schedules: authenticated users can read
CREATE POLICY "Authenticated read access for legislation_schedules" ON legislation_schedules
    FOR SELECT 
    TO authenticated
    USING (true);

-- =============================================================================
-- CREATE POLICIES FOR EMBEDDING TABLES
-- =============================================================================

-- Case embeddings (Cohere): authenticated users can read, service role can write
CREATE POLICY "Authenticated read access for case_embeddings_cohere" ON case_embeddings_cohere
    FOR SELECT 
    TO authenticated
    USING (true);

CREATE POLICY "Service role write access for case_embeddings_cohere" ON case_embeddings_cohere
    FOR ALL 
    USING (auth.role() = 'service_role');

-- Case embeddings (OpenAI): authenticated users can read, service role can write
CREATE POLICY "Authenticated read access for case_embeddings_openai" ON case_embeddings_openai
    FOR SELECT 
    TO authenticated
    USING (true);

CREATE POLICY "Service role write access for case_embeddings_openai" ON case_embeddings_openai
    FOR ALL 
    USING (auth.role() = 'service_role');

-- Legislation embeddings (Cohere): authenticated users can read, service role can write
CREATE POLICY "Authenticated read access for legislation_embeddings_cohere" ON legislation_embeddings_cohere
    FOR SELECT 
    TO authenticated
    USING (true);

CREATE POLICY "Service role write access for legislation_embeddings_cohere" ON legislation_embeddings_cohere
    FOR ALL 
    USING (auth.role() = 'service_role');

-- Legislation embeddings (OpenAI): authenticated users can read, service role can write
CREATE POLICY "Authenticated read access for legislation_embeddings_openai" ON legislation_embeddings_openai
    FOR SELECT 
    TO authenticated
    USING (true);

CREATE POLICY "Service role write access for legislation_embeddings_openai" ON legislation_embeddings_openai
    FOR ALL 
    USING (auth.role() = 'service_role');

-- Headnote corpus: authenticated users can read, service role can write
CREATE POLICY "Authenticated read access for headnote_corpus" ON headnote_corpus
    FOR SELECT 
    TO authenticated
    USING (true);

CREATE POLICY "Service role write access for headnote_corpus" ON headnote_corpus
    FOR ALL 
    USING (auth.role() = 'service_role');

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON POLICY "Authenticated read access for courts" ON courts IS 'Only authenticated users can read court data';
COMMENT ON POLICY "Authenticated read access for court_cases" ON court_cases IS 'Only authenticated users can read case data';
COMMENT ON POLICY "Authenticated read access for legislation" ON legislation IS 'Only authenticated users can read legislation data';
COMMENT ON POLICY "Authenticated read access for legislation_sections" ON legislation_sections IS 'Only authenticated users can read legislation sections';
COMMENT ON POLICY "Authenticated read access for legislation_schedules" ON legislation_schedules IS 'Only authenticated users can read legislation schedules';
