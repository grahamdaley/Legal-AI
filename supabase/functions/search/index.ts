import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders, handleCors } from "../_shared/cors.ts";
import { badRequest, serverError } from "../_shared/errors.ts";
import { getSupabaseClient } from "../_shared/db.ts";
import { generateEmbedding } from "../_shared/bedrock.ts";
import type { SearchRequest, SearchResponse, CaseResult, LegislationResult, SearchResult } from "./types.ts";

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;
const DEFAULT_SEMANTIC_WEIGHT = 0.7;

serve(async (req: Request) => {
  const corsResponse = handleCors(req);
  if (corsResponse) return corsResponse;

  if (req.method !== "POST") {
    return badRequest("Method not allowed. Use POST.");
  }

  const startTime = performance.now();

  try {
    const body: SearchRequest = await req.json();

    if (!body.query || typeof body.query !== "string" || body.query.trim().length === 0) {
      return badRequest("Query is required and must be a non-empty string");
    }

    const query = body.query.trim();
    const searchType = body.type || "all";
    const filters = body.filters || {};
    const options = body.options || {};

    const limit = Math.min(options.limit || DEFAULT_LIMIT, MAX_LIMIT);
    const offset = options.offset || 0;
    const searchMode = options.searchMode || "hybrid";
    const semanticWeight = options.semanticWeight ?? DEFAULT_SEMANTIC_WEIGHT;

    const embeddingStart = performance.now();
    const embedding = await generateEmbedding(query);
    const embeddingMs = performance.now() - embeddingStart;

    const supabase = getSupabaseClient();
    const searchStart = performance.now();

    const results: SearchResult[] = [];
    let totalCount = 0;

    if (searchType === "cases" || searchType === "all") {
      const caseResults = await searchCases(
        supabase,
        query,
        embedding,
        searchMode,
        semanticWeight,
        filters.court || null,
        filters.yearFrom || null,
        filters.yearTo || null,
        limit,
        offset
      );
      results.push(...caseResults.map((r) => ({ ...r, result_type: "case" as const })));
      totalCount += caseResults.length;
    }

    if (searchType === "legislation" || searchType === "all") {
      const legResults = await searchLegislation(
        supabase,
        query,
        embedding,
        searchMode,
        semanticWeight,
        filters.legislationType || null,
        limit,
        offset
      );
      results.push(...legResults.map((r) => ({ ...r, result_type: "legislation" as const })));
      totalCount += legResults.length;
    }

    if (searchType === "all") {
      results.sort((a, b) => {
        const scoreA = "combined_score" in a ? a.combined_score : a.similarity_score || 0;
        const scoreB = "combined_score" in b ? b.combined_score : b.similarity_score || 0;
        return (scoreB || 0) - (scoreA || 0);
      });
      results.splice(limit);
    }

    const searchMs = performance.now() - searchStart;
    const totalMs = performance.now() - startTime;

    const response: SearchResponse = {
      results,
      total: totalCount,
      query,
      searchMode,
      timing: {
        embedding_ms: Math.round(embeddingMs),
        search_ms: Math.round(searchMs),
        total_ms: Math.round(totalMs),
      },
    };

    return new Response(JSON.stringify(response), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Search error:", error);
    return serverError(
      error instanceof Error ? error.message : "An unexpected error occurred"
    );
  }
});

async function searchCases(
  supabase: ReturnType<typeof getSupabaseClient>,
  queryText: string,
  embedding: number[],
  searchMode: string,
  semanticWeight: number,
  filterCourt: string | null,
  filterYearFrom: number | null,
  filterYearTo: number | null,
  limit: number,
  _offset: number
): Promise<CaseResult[]> {
  const embeddingStr = `[${embedding.join(",")}]`;

  if (searchMode === "semantic") {
    const { data, error } = await supabase.rpc("search_cases_semantic", {
      query_embedding: embeddingStr,
      match_count: limit,
      filter_court: filterCourt,
      filter_year_from: filterYearFrom,
      filter_year_to: filterYearTo,
    });

    if (error) throw new Error(`Case search failed: ${error.message}`);
    return (data || []) as CaseResult[];
  } else {
    const { data, error } = await supabase.rpc("search_cases_hybrid", {
      query_text: queryText,
      query_embedding: embeddingStr,
      match_count: limit,
      semantic_weight: semanticWeight,
      filter_court: filterCourt,
      filter_year_from: filterYearFrom,
      filter_year_to: filterYearTo,
    });

    if (error) throw new Error(`Case search failed: ${error.message}`);
    return (data || []) as CaseResult[];
  }
}

async function searchLegislation(
  supabase: ReturnType<typeof getSupabaseClient>,
  queryText: string,
  embedding: number[],
  searchMode: string,
  semanticWeight: number,
  filterType: string | null,
  limit: number,
  _offset: number
): Promise<LegislationResult[]> {
  const embeddingStr = `[${embedding.join(",")}]`;

  if (searchMode === "semantic") {
    const { data, error } = await supabase.rpc("search_legislation_semantic", {
      query_embedding: embeddingStr,
      match_count: limit,
      filter_type: filterType,
    });

    if (error) throw new Error(`Legislation search failed: ${error.message}`);
    return (data || []) as LegislationResult[];
  } else {
    const { data, error } = await supabase.rpc("search_legislation_hybrid", {
      query_text: queryText,
      query_embedding: embeddingStr,
      match_count: limit,
      semantic_weight: semanticWeight,
      filter_type: filterType,
    });

    if (error) throw new Error(`Legislation search failed: ${error.message}`);
    return (data || []) as LegislationResult[];
  }
}
