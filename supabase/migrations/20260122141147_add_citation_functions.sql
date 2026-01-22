-- Citation network functions for finding cases that cite and are cited by a given case

-- Get cases cited BY a given case (outgoing citations)
-- Uses the cited_cases JSONB array stored on each case
CREATE OR REPLACE FUNCTION get_cited_cases(p_case_id UUID)
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
    v_cited_citations JSONB;
BEGIN
    -- Get the cited_cases array for this case
    SELECT cc.cited_cases INTO v_cited_citations
    FROM court_cases cc
    WHERE cc.id = p_case_id;
    
    IF v_cited_citations IS NULL OR jsonb_array_length(v_cited_citations) = 0 THEN
        RETURN;
    END IF;
    
    -- Find cases in our database that match the cited citations
    RETURN QUERY
    SELECT 
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_code,
        cc.decision_date
    FROM court_cases cc
    WHERE cc.neutral_citation = ANY(
        SELECT jsonb_array_elements_text(v_cited_citations)
    )
    ORDER BY cc.decision_date DESC NULLS LAST;
END;
$$;

-- Get cases that CITE a given case (incoming citations / cited by)
-- Searches the cited_cases JSONB array of all cases for the target citation
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
BEGIN
    -- Get the neutral citation for this case
    SELECT cc.neutral_citation INTO v_neutral_citation
    FROM court_cases cc
    WHERE cc.id = p_case_id;
    
    IF v_neutral_citation IS NULL THEN
        RETURN;
    END IF;
    
    -- Find cases that cite this case
    RETURN QUERY
    SELECT 
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_code,
        cc.decision_date
    FROM court_cases cc
    WHERE cc.cited_cases @> to_jsonb(v_neutral_citation)
      AND cc.id != p_case_id  -- Exclude self
    ORDER BY cc.decision_date DESC NULLS LAST;
END;
$$;

-- Create GIN index on cited_cases for faster reverse lookups
CREATE INDEX IF NOT EXISTS idx_court_cases_cited_cases_gin 
    ON court_cases USING GIN (cited_cases);
