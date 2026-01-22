-- Add law_report_citations column to store alternate citation formats
-- This enables matching citations like [1996] 2 HKLR 401 to cases in our database

-- Add the new column
ALTER TABLE court_cases 
ADD COLUMN IF NOT EXISTS law_report_citations JSONB DEFAULT '[]'::JSONB;

-- Create GIN index for fast lookups
CREATE INDEX IF NOT EXISTS idx_court_cases_law_report_citations_gin 
    ON court_cases USING GIN (law_report_citations);

-- Update get_cited_cases to also match against law_report_citations
DROP FUNCTION IF EXISTS get_cited_cases(UUID);

CREATE OR REPLACE FUNCTION get_cited_cases(p_case_id UUID)
RETURNS TABLE (
    citation_text TEXT,
    id UUID,
    neutral_citation TEXT,
    case_name TEXT,
    court_code TEXT,
    decision_date DATE,
    is_in_database BOOLEAN
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_cited_citations JSONB;
BEGIN
    -- Get the cited_cases array for this case
    SELECT cc.cited_cases INTO v_cited_citations
    FROM court_cases cc
    WHERE cc.id = p_case_id;
    
    IF v_cited_citations IS NULL OR jsonb_array_length(v_cited_citations) = 0 THEN
        RETURN;
    END IF;
    
    -- Return all citations with match info
    -- Match against both neutral_citation AND law_report_citations
    RETURN QUERY
    SELECT 
        cit.citation AS citation_text,
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_code,
        cc.decision_date,
        (cc.id IS NOT NULL) AS is_in_database
    FROM jsonb_array_elements_text(v_cited_citations) AS cit(citation)
    LEFT JOIN court_cases cc ON (
        cc.neutral_citation = cit.citation
        OR cc.law_report_citations @> to_jsonb(cit.citation)
    )
    ORDER BY (cc.id IS NOT NULL) DESC, cit.citation;
END;
$$;

-- Update get_citing_cases to also search for law_report_citations
DROP FUNCTION IF EXISTS get_citing_cases(UUID);

CREATE OR REPLACE FUNCTION get_citing_cases(p_case_id UUID)
RETURNS TABLE (
    id UUID,
    neutral_citation TEXT,
    case_name TEXT,
    court_code TEXT,
    decision_date DATE
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_neutral_citation TEXT;
    v_law_report_citations JSONB;
BEGIN
    -- Get the neutral citation and law report citations for this case
    SELECT cc.neutral_citation, cc.law_report_citations 
    INTO v_neutral_citation, v_law_report_citations
    FROM court_cases cc
    WHERE cc.id = p_case_id;
    
    IF v_neutral_citation IS NULL AND (v_law_report_citations IS NULL OR jsonb_array_length(v_law_report_citations) = 0) THEN
        RETURN;
    END IF;
    
    -- Find cases that cite this case (by neutral citation or any law report citation)
    RETURN QUERY
    SELECT DISTINCT
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_code,
        cc.decision_date
    FROM court_cases cc
    WHERE cc.id != p_case_id
      AND (
        -- Match by neutral citation
        (v_neutral_citation IS NOT NULL AND cc.cited_cases @> to_jsonb(v_neutral_citation))
        -- Match by any law report citation
        OR (v_law_report_citations IS NOT NULL AND jsonb_array_length(v_law_report_citations) > 0 AND EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(v_law_report_citations) AS lrc(cit)
            WHERE cc.cited_cases @> to_jsonb(lrc.cit)
        ))
      )
    ORDER BY cc.decision_date DESC NULLS LAST;
END;
$$;
