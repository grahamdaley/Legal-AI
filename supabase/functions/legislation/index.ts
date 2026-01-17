import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders, handleCors } from "../_shared/cors.ts";
import { badRequest, notFound, serverError, unauthorized } from "../_shared/errors.ts";
import { getSupabaseClient, verifyAuthHeader } from "../_shared/db.ts";

interface LegislationSection {
  id: string;
  section_number: string;
  title: string | null;
  content: string;
  sort_order: number;
}

interface LegislationSchedule {
  id: string;
  schedule_number: string;
  title: string | null;
  content: string | null;
  sort_order: number;
}

interface LegislationDetailResponse {
  id: string;
  chapter_number: string;
  title_en: string | null;
  title_zh: string | null;
  type: string;
  status: string;
  enactment_date: string | null;
  commencement_date: string | null;
  long_title: string | null;
  preamble: string | null;
  source_url: string;
  pdf_url: string | null;
  sections: LegislationSection[];
  schedules: LegislationSchedule[];
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
  const userId = verifyAuthHeader(authHeader);
  if (!userId) {
    return unauthorized("Invalid or expired token");
  }

  try {
    const url = new URL(req.url);
    const pathParts = url.pathname.split("/").filter(Boolean);
    const legislationId = pathParts[pathParts.length - 1];

    if (!legislationId || !UUID_REGEX.test(legislationId)) {
      return badRequest("Invalid legislation ID. Must be a valid UUID.");
    }

    const supabase = getSupabaseClient();

    const { data: legData, error: legError } = await supabase
      .from("legislation")
      .select(`
        id,
        chapter_number,
        title_en,
        title_zh,
        type,
        status,
        enactment_date,
        commencement_date,
        long_title,
        preamble,
        source_url,
        pdf_url
      `)
      .eq("id", legislationId)
      .single();

    if (legError) {
      if (legError.code === "PGRST116") {
        return notFound(`Legislation with ID ${legislationId} not found`);
      }
      throw new Error(`Database error: ${legError.message}`);
    }

    if (!legData) {
      return notFound(`Legislation with ID ${legislationId} not found`);
    }

    const { data: sectionsData, error: sectionsError } = await supabase
      .from("legislation_sections")
      .select("id, section_number, title, content, sort_order")
      .eq("legislation_id", legislationId)
      .order("sort_order", { ascending: true });

    if (sectionsError) {
      throw new Error(`Failed to fetch sections: ${sectionsError.message}`);
    }

    const { data: schedulesData, error: schedulesError } = await supabase
      .from("legislation_schedules")
      .select("id, schedule_number, title, content, sort_order")
      .eq("legislation_id", legislationId)
      .order("sort_order", { ascending: true });

    if (schedulesError) {
      throw new Error(`Failed to fetch schedules: ${schedulesError.message}`);
    }

    const response: LegislationDetailResponse = {
      id: legData.id,
      chapter_number: legData.chapter_number,
      title_en: legData.title_en,
      title_zh: legData.title_zh,
      type: legData.type,
      status: legData.status,
      enactment_date: legData.enactment_date,
      commencement_date: legData.commencement_date,
      long_title: legData.long_title,
      preamble: legData.preamble,
      source_url: legData.source_url,
      pdf_url: legData.pdf_url,
      sections: (sectionsData || []) as LegislationSection[],
      schedules: (schedulesData || []) as LegislationSchedule[],
    };

    return new Response(JSON.stringify(response), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Legislation detail error:", error);
    return serverError(
      error instanceof Error ? error.message : "An unexpected error occurred"
    );
  }
});
