-- Improve citation display by returning all citations with match status
-- This allows showing citations even when they don't exist in our database

-- Drop and recreate get_cited_cases to return all citations with linked case info
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
    LEFT JOIN court_cases cc ON cc.neutral_citation = cit.citation
    ORDER BY (cc.id IS NOT NULL) DESC, cit.citation;
END;
$$;
