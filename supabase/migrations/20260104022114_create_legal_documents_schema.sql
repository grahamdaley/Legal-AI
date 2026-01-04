-- Legal Documents Schema for Hong Kong Legal AI
-- This migration creates tables for court cases and legislation

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =============================================================================
-- COURT CASES (Judiciary)
-- =============================================================================

-- Courts lookup table
CREATE TABLE IF NOT EXISTS courts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code TEXT UNIQUE NOT NULL,
    name_en TEXT NOT NULL,
    name_zh TEXT,
    hierarchy_level INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert Hong Kong courts
INSERT INTO courts (code, name_en, name_zh, hierarchy_level) VALUES
    ('CFA', 'Court of Final Appeal', '終審法院', 1),
    ('CA', 'Court of Appeal', '上訴法庭', 2),
    ('CFI', 'Court of First Instance', '原訟法庭', 3),
    ('DC', 'District Court', '區域法院', 4),
    ('FC', 'Family Court', '家事法庭', 4),
    ('LT', 'Lands Tribunal', '土地審裁處', 5),
    ('LAB', 'Labour Tribunal', '勞資審裁處', 5),
    ('SCT', 'Small Claims Tribunal', '小額錢債審裁處', 6),
    ('HKCFI', 'High Court - Court of First Instance', '高等法院原訟法庭', 3),
    ('HKCA', 'High Court - Court of Appeal', '高等法院上訴法庭', 2),
    ('HKCFA', 'Court of Final Appeal', '終審法院', 1)
ON CONFLICT (code) DO NOTHING;

-- Court cases table
CREATE TABLE IF NOT EXISTS court_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Identifiers
    neutral_citation TEXT UNIQUE,
    case_number TEXT NOT NULL,
    case_name TEXT,
    
    -- Court and date
    court_id UUID REFERENCES courts(id),
    court_code TEXT,
    decision_date DATE,
    
    -- Judges (stored as JSONB array)
    judges JSONB DEFAULT '[]'::JSONB,
    
    -- Parties (stored as JSONB object with plaintiff/defendant/appellant/respondent)
    parties JSONB DEFAULT '{}'::JSONB,
    
    -- Content
    headnote TEXT,
    catchwords JSONB DEFAULT '[]'::JSONB,
    full_text TEXT,
    word_count INTEGER DEFAULT 0,
    language TEXT DEFAULT 'en',
    
    -- Citations
    cited_cases JSONB DEFAULT '[]'::JSONB,
    
    -- Source
    source_url TEXT NOT NULL,
    pdf_url TEXT,
    raw_html TEXT,
    
    -- Metadata
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- For vector search (to be populated by embedding job)
    embedding VECTOR(3072),
    
    -- Constraints
    CONSTRAINT court_cases_case_number_unique UNIQUE (case_number, court_code)
);

-- Indexes for court cases
CREATE INDEX IF NOT EXISTS idx_court_cases_neutral_citation ON court_cases(neutral_citation);
CREATE INDEX IF NOT EXISTS idx_court_cases_case_number ON court_cases(case_number);
CREATE INDEX IF NOT EXISTS idx_court_cases_court_id ON court_cases(court_id);
CREATE INDEX IF NOT EXISTS idx_court_cases_decision_date ON court_cases(decision_date);
CREATE INDEX IF NOT EXISTS idx_court_cases_language ON court_cases(language);
CREATE INDEX IF NOT EXISTS idx_court_cases_scraped_at ON court_cases(scraped_at);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_court_cases_full_text_search 
    ON court_cases USING GIN (to_tsvector('english', COALESCE(case_name, '') || ' ' || COALESCE(headnote, '') || ' ' || COALESCE(full_text, '')));

-- =============================================================================
-- LEGISLATION (eLegislation)
-- =============================================================================

-- Legislation types
CREATE TYPE legislation_type AS ENUM (
    'ordinance',
    'regulation',
    'rule',
    'order',
    'notice',
    'bylaw',
    'subsidiary'
);

-- Legislation status
CREATE TYPE legislation_status AS ENUM (
    'active',
    'repealed',
    'amended',
    'expired',
    'not_yet_in_force'
);

-- Main legislation table
CREATE TABLE IF NOT EXISTS legislation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Identifiers
    chapter_number TEXT NOT NULL,
    title_en TEXT,
    title_zh TEXT,
    
    -- Classification
    type legislation_type NOT NULL DEFAULT 'ordinance',
    status legislation_status NOT NULL DEFAULT 'active',
    
    -- Dates
    enactment_date DATE,
    commencement_date DATE,
    version_date DATE,
    
    -- Content
    long_title TEXT,
    preamble TEXT,
    
    -- Source
    source_url TEXT NOT NULL,
    pdf_url TEXT,
    raw_html TEXT,
    
    -- Metadata
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- For vector search
    embedding VECTOR(3072),
    
    -- Constraints
    CONSTRAINT legislation_chapter_unique UNIQUE (chapter_number, version_date)
);

-- Legislation sections table
CREATE TABLE IF NOT EXISTS legislation_sections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    legislation_id UUID NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    
    -- Section identifiers
    section_number TEXT NOT NULL,
    title TEXT,
    
    -- Content
    content TEXT NOT NULL,
    
    -- Ordering
    sort_order INTEGER NOT NULL DEFAULT 0,
    
    -- Source (for deep linking)
    source_url TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- For vector search
    embedding VECTOR(3072),
    
    -- Constraints
    CONSTRAINT legislation_sections_unique UNIQUE (legislation_id, section_number)
);

-- Legislation schedules table
CREATE TABLE IF NOT EXISTS legislation_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    legislation_id UUID NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    
    -- Schedule identifiers
    schedule_number TEXT NOT NULL,
    title TEXT,
    
    -- Content
    content TEXT,
    
    -- Ordering
    sort_order INTEGER NOT NULL DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT legislation_schedules_unique UNIQUE (legislation_id, schedule_number)
);

-- Indexes for legislation
CREATE INDEX IF NOT EXISTS idx_legislation_chapter_number ON legislation(chapter_number);
CREATE INDEX IF NOT EXISTS idx_legislation_type ON legislation(type);
CREATE INDEX IF NOT EXISTS idx_legislation_status ON legislation(status);
CREATE INDEX IF NOT EXISTS idx_legislation_scraped_at ON legislation(scraped_at);

-- Indexes for legislation sections
CREATE INDEX IF NOT EXISTS idx_legislation_sections_legislation_id ON legislation_sections(legislation_id);
CREATE INDEX IF NOT EXISTS idx_legislation_sections_section_number ON legislation_sections(section_number);

-- Full-text search index for legislation
CREATE INDEX IF NOT EXISTS idx_legislation_full_text_search 
    ON legislation USING GIN (to_tsvector('english', COALESCE(title_en, '') || ' ' || COALESCE(long_title, '') || ' ' || COALESCE(preamble, '')));

CREATE INDEX IF NOT EXISTS idx_legislation_sections_full_text_search 
    ON legislation_sections USING GIN (to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(content, '')));

-- =============================================================================
-- INGESTION TRACKING
-- =============================================================================

-- Track ingestion jobs for idempotency
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL,  -- 'judiciary' or 'elegislation'
    file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    records_total INTEGER DEFAULT 0,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ingestion_jobs_file_unique UNIQUE (source, file_path)
);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE courts ENABLE ROW LEVEL SECURITY;
ALTER TABLE court_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE legislation ENABLE ROW LEVEL SECURITY;
ALTER TABLE legislation_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE legislation_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_jobs ENABLE ROW LEVEL SECURITY;

-- Public read access for legal documents (they are public records)
CREATE POLICY "Public read access for courts" ON courts
    FOR SELECT USING (true);

CREATE POLICY "Public read access for court_cases" ON court_cases
    FOR SELECT USING (true);

CREATE POLICY "Public read access for legislation" ON legislation
    FOR SELECT USING (true);

CREATE POLICY "Public read access for legislation_sections" ON legislation_sections
    FOR SELECT USING (true);

CREATE POLICY "Public read access for legislation_schedules" ON legislation_schedules
    FOR SELECT USING (true);

-- Service role only for write operations
CREATE POLICY "Service role write access for courts" ON courts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role write access for court_cases" ON court_cases
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role write access for legislation" ON legislation
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role write access for legislation_sections" ON legislation_sections
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role write access for legislation_schedules" ON legislation_schedules
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role access for ingestion_jobs" ON ingestion_jobs
    FOR ALL USING (auth.role() = 'service_role');

-- =============================================================================
-- UPDATED_AT TRIGGER
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_court_cases_updated_at
    BEFORE UPDATE ON court_cases
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_legislation_updated_at
    BEFORE UPDATE ON legislation
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_legislation_sections_updated_at
    BEFORE UPDATE ON legislation_sections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE courts IS 'Hong Kong court hierarchy lookup table';
COMMENT ON TABLE court_cases IS 'Court judgments scraped from the Judiciary Legal Reference System';
COMMENT ON TABLE legislation IS 'Hong Kong legislation scraped from eLegislation';
COMMENT ON TABLE legislation_sections IS 'Individual sections within legislation';
COMMENT ON TABLE legislation_schedules IS 'Schedules attached to legislation';
COMMENT ON TABLE ingestion_jobs IS 'Tracks JSONL file ingestion for idempotency';