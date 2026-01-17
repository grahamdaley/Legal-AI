import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders, handleCors } from "../_shared/cors.ts";
import { badRequest, serverError } from "../_shared/errors.ts";
import { getSupabaseClient } from "../_shared/db.ts";

interface Suggestion {
  text: string;
  type: "citation" | "case_name" | "legal_term" | "legislation";
  metadata?: {
    id?: string;
    court?: string;
  };
}

interface SuggestionsResponse {
  suggestions: Suggestion[];
}

const MAX_SUGGESTIONS = 10;
const MIN_QUERY_LENGTH = 2;

serve(async (req: Request) => {
  const corsResponse = handleCors(req);
  if (corsResponse) return corsResponse;

  if (req.method !== "GET") {
    return badRequest("Method not allowed. Use GET.");
  }

  try {
    const url = new URL(req.url);
    const query = url.searchParams.get("q")?.trim() || "";
    const type = url.searchParams.get("type") || "all";

    if (query.length < MIN_QUERY_LENGTH) {
      return new Response(JSON.stringify({ suggestions: [] }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const supabase = getSupabaseClient();
    const suggestions: Suggestion[] = [];

    if (type === "cases" || type === "all") {
      const citationPattern = query.match(/^\[?\d{4}\]?\s*HK/i);
      if (citationPattern) {
        const { data: citationMatches } = await supabase
          .from("court_cases")
          .select("id, neutral_citation, court_code")
          .ilike("neutral_citation", `%${query}%`)
          .limit(5);

        if (citationMatches) {
          for (const match of citationMatches) {
            suggestions.push({
              text: match.neutral_citation,
              type: "citation",
              metadata: { id: match.id, court: match.court_code },
            });
          }
        }
      }

      const { data: caseNameMatches } = await supabase
        .from("court_cases")
        .select("id, case_name, court_code")
        .ilike("case_name", `%${query}%`)
        .limit(5);

      if (caseNameMatches) {
        for (const match of caseNameMatches) {
          if (match.case_name && !suggestions.some((s) => s.text === match.case_name)) {
            suggestions.push({
              text: match.case_name,
              type: "case_name",
              metadata: { id: match.id, court: match.court_code },
            });
          }
        }
      }
    }

    if (type === "legislation" || type === "all") {
      const chapterPattern = query.match(/^cap\.?\s*\d+/i);
      if (chapterPattern) {
        const { data: chapterMatches } = await supabase
          .from("legislation")
          .select("id, chapter_number, title_en")
          .ilike("chapter_number", `%${query.replace(/cap\.?\s*/i, "")}%`)
          .limit(5);

        if (chapterMatches) {
          for (const match of chapterMatches) {
            suggestions.push({
              text: `Cap. ${match.chapter_number} - ${match.title_en}`,
              type: "legislation",
              metadata: { id: match.id },
            });
          }
        }
      } else {
        const { data: titleMatches } = await supabase
          .from("legislation")
          .select("id, chapter_number, title_en")
          .ilike("title_en", `%${query}%`)
          .limit(5);

        if (titleMatches) {
          for (const match of titleMatches) {
            if (!suggestions.some((s) => s.metadata?.id === match.id)) {
              suggestions.push({
                text: `Cap. ${match.chapter_number} - ${match.title_en}`,
                type: "legislation",
                metadata: { id: match.id },
              });
            }
          }
        }
      }
    }

    const legalTerms = getLegalTermSuggestions(query);
    for (const term of legalTerms) {
      if (suggestions.length < MAX_SUGGESTIONS) {
        suggestions.push({
          text: term,
          type: "legal_term",
        });
      }
    }

    const response: SuggestionsResponse = {
      suggestions: suggestions.slice(0, MAX_SUGGESTIONS),
    };

    return new Response(JSON.stringify(response), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Suggestions error:", error);
    return serverError(
      error instanceof Error ? error.message : "An unexpected error occurred"
    );
  }
});

function getLegalTermSuggestions(query: string): string[] {
  const legalTerms = [
    "judicial review",
    "habeas corpus",
    "ultra vires",
    "res judicata",
    "stare decisis",
    "prima facie",
    "mens rea",
    "actus reus",
    "negligence",
    "duty of care",
    "breach of contract",
    "specific performance",
    "injunction",
    "damages",
    "tort",
    "defamation",
    "libel",
    "slander",
    "wrongful dismissal",
    "unfair dismissal",
    "personal injury",
    "professional negligence",
    "fiduciary duty",
    "constructive trust",
    "equitable estoppel",
    "promissory estoppel",
    "frustration of contract",
    "force majeure",
    "misrepresentation",
    "undue influence",
    "duress",
    "unconscionable bargain",
    "restraint of trade",
    "intellectual property",
    "copyright infringement",
    "trademark",
    "passing off",
    "winding up",
    "insolvency",
    "bankruptcy",
    "judicial sale",
    "mareva injunction",
    "anton piller order",
    "discovery",
    "interrogatories",
    "summary judgment",
    "striking out",
    "leave to appeal",
    "costs order",
    "taxation of costs",
  ];

  const queryLower = query.toLowerCase();
  return legalTerms
    .filter((term) => term.includes(queryLower))
    .slice(0, 3);
}
