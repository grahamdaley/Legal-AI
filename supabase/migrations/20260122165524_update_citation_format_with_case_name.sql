-- Update citation functions to handle new format where cited_cases is an array of objects
-- Each object has: { "citation": "...", "case_name": "..." }
-- This enables displaying citations with case names like "Woolmington v D.P.P. [1935] AC 462"

DROP FUNCTION IF EXISTS get_cited_cases(UUID);

CREATE OR REPLACE FUNCTION get_cited_cases(p_case_id UUID)
RETURNS TABLE (
    citation_text TEXT,
    cited_case_name TEXT,
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
    
    -- Handle both old format (array of strings) and new format (array of objects)
    -- New format: [{"citation": "...", "case_name": "..."}]
    -- Old format: ["citation1", "citation2"]
    RETURN QUERY
    SELECT 
        COALESCE(cit.obj->>'citation', cit.obj#>>'{}') AS citation_text,
        cit.obj->>'case_name' AS cited_case_name,
        cc.id,
        cc.neutral_citation,
        cc.case_name,
        cc.court_code,
        cc.decision_date,
        (cc.id IS NOT NULL) AS is_in_database
    FROM jsonb_array_elements(v_cited_citations) AS cit(obj)
    LEFT JOIN court_cases cc ON (
        cc.neutral_citation = COALESCE(cit.obj->>'citation', cit.obj#>>'{}')
        OR cc.law_report_citations @> to_jsonb(COALESCE(cit.obj->>'citation', cit.obj#>>'{}'))
    )
    ORDER BY (cc.id IS NOT NULL) DESC, COALESCE(cit.obj->>'citation', cit.obj#>>'{}');
END;
$$;

-- Update get_citing_cases to handle both old and new formats
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
    -- Handle both old format (array of strings) and new format (array of objects)
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
        -- Match by neutral citation (check both formats)
        (v_neutral_citation IS NOT NULL AND (
            cc.cited_cases @> to_jsonb(v_neutral_citation)
            OR EXISTS (
                SELECT 1 FROM jsonb_array_elements(cc.cited_cases) AS elem
                WHERE elem->>'citation' = v_neutral_citation
            )
        ))
        -- Match by any law report citation (check both formats)
        OR (v_law_report_citations IS NOT NULL AND jsonb_array_length(v_law_report_citations) > 0 AND EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(v_law_report_citations) AS lrc(cit)
            WHERE cc.cited_cases @> to_jsonb(lrc.cit)
               OR EXISTS (
                   SELECT 1 FROM jsonb_array_elements(cc.cited_cases) AS elem
                   WHERE elem->>'citation' = lrc.cit
               )
        ))
      )
    ORDER BY cc.decision_date DESC NULLS LAST;
END;
$$;
