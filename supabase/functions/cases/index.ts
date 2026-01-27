import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders, handleCors } from "../_shared/cors.ts";
import { badRequest, notFound, serverError, unauthorized } from "../_shared/errors.ts";
import { getSupabaseClient, verifyAuthHeader } from "../_shared/db.ts";

interface CaseDetailResponse {
  id: string;
  neutral_citation: string | null;
  case_number: string;
  case_name: string | null;
  court: {
    id: string;
    name_en: string;
    code: string;
  } | null;
  decision_date: string | null;
  judges: string[];
  parties: Record<string, unknown>;
  headnote: string | null;
  full_text: string | null;
  source_url: string;
  pdf_url: string | null;
}

interface CitedCase {
  id: string | null;
  citation_text: string;
  cited_case_name: string | null;
  neutral_citation: string | null;
  case_name: string | null;
  court_code: string | null;
  decision_date: string | null;
  is_in_database: boolean;
}

interface CitingCase {
  id: string;
  neutral_citation: string | null;
  case_name: string | null;
  court_code: string | null;
  decision_date: string | null;
}

interface CitationsResponse {
  cited_cases: CitedCase[];
  citing_cases: CitingCase[];
}

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

serve(async (req: Request) => {
  const corsResponse = handleCors(req);
  if (corsResponse) return corsResponse;

  if (req.method !== "GET") {
    return badRequest("Method not allowed. Use GET.");
  }

  // Require authentication
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) {
    return unauthorized("Authentication required");
  }

  // Verify the user is authenticated
  const userId = await verifyAuthHeader(authHeader);
  if (!userId) {
    return unauthorized("Invalid or expired token");
  }

  try {
    const url = new URL(req.url);
    const pathParts = url.pathname.split("/").filter(Boolean);
    
    // Check if this is a citations request: /cases/{id}/citations
    const isCitationsRequest = pathParts[pathParts.length - 1] === "citations";
    const caseId = isCitationsRequest 
      ? pathParts[pathParts.length - 2] 
      : pathParts[pathParts.length - 1];

    if (!caseId || !UUID_REGEX.test(caseId)) {
      return badRequest("Invalid case ID. Must be a valid UUID.");
    }

    const supabase = getSupabaseClient();

    // Handle citations request
    if (isCitationsRequest) {
      // Get cases cited BY this case
      const { data: citedCases, error: citedError } = await supabase
        .rpc("get_cited_cases", { p_case_id: caseId });

      if (citedError) {
        console.error("Error fetching cited cases:", citedError);
      }

      // Get cases that CITE this case
      const { data: citingCases, error: citingError } = await supabase
        .rpc("get_citing_cases", { p_case_id: caseId });

      if (citingError) {
        console.error("Error fetching citing cases:", citingError);
      }

      const response: CitationsResponse = {
        cited_cases: (citedCases || []).map((c: CitedCase) => ({
          id: c.id,
          citation_text: c.citation_text,
          cited_case_name: c.cited_case_name,
          neutral_citation: c.neutral_citation,
          case_name: c.case_name,
          court_code: c.court_code,
          decision_date: c.decision_date,
          is_in_database: c.is_in_database,
        })),
        citing_cases: (citingCases || []).map((c: CitingCase) => ({
          id: c.id,
          neutral_citation: c.neutral_citation,
          case_name: c.case_name,
          court_code: c.court_code,
          decision_date: c.decision_date,
        })),
      };

      return new Response(JSON.stringify(response), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { data: caseData, error: caseError } = await supabase
      .from("court_cases")
      .select(`
        id,
        neutral_citation,
        case_number,
        case_name,
        court_id,
        court_code,
        decision_date,
        judges,
        parties,
        headnote,
        full_text,
        source_url,
        pdf_url
      `)
      .eq("id", caseId)
      .single();

    if (caseError) {
      if (caseError.code === "PGRST116") {
        return notFound(`Case with ID ${caseId} not found`);
      }
      throw new Error(`Database error: ${caseError.message}`);
    }

    if (!caseData) {
      return notFound(`Case with ID ${caseId} not found`);
    }

    let court = null;
    if (caseData.court_id) {
      const { data: courtData } = await supabase
        .from("courts")
        .select("id, name_en, code")
        .eq("id", caseData.court_id)
        .single();

      if (courtData) {
        court = courtData;
      }
    }

    const response: CaseDetailResponse = {
      id: caseData.id,
      neutral_citation: caseData.neutral_citation,
      case_number: caseData.case_number,
      case_name: caseData.case_name,
      court,
      decision_date: caseData.decision_date,
      judges: Array.isArray(caseData.judges) ? caseData.judges : [],
      parties: typeof caseData.parties === "object" && caseData.parties !== null 
        ? caseData.parties as Record<string, unknown>
        : {},
      headnote: caseData.headnote,
      full_text: caseData.full_text,
      source_url: caseData.source_url,
      pdf_url: caseData.pdf_url,
    };

    return new Response(JSON.stringify(response), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Case detail error:", error);
    return serverError(
      error instanceof Error ? error.message : "An unexpected error occurred"
    );
  }
});
