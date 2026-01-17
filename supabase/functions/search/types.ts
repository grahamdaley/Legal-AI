export interface SearchRequest {
  query: string;
  type: "cases" | "legislation" | "all";
  filters?: {
    court?: string;
    yearFrom?: number;
    yearTo?: number;
    legislationType?: string;
  };
  options?: {
    limit?: number;
    offset?: number;
    searchMode?: "semantic" | "hybrid";
    semanticWeight?: number;
  };
}

export interface CaseResult {
  id: string;
  neutral_citation: string | null;
  case_name: string | null;
  court_id: string | null;
  court_code: string | null;
  decision_date: string | null;
  headnote: string | null;
  similarity_score?: number;
  semantic_score?: number;
  fts_score?: number;
  combined_score?: number;
}

export interface LegislationResult {
  section_id: string;
  legislation_id: string;
  chapter_number: string;
  title_en: string | null;
  section_number: string;
  section_title: string | null;
  content_snippet: string | null;
  similarity_score?: number;
  semantic_score?: number;
  fts_score?: number;
  combined_score?: number;
}

export type SearchResult = 
  | (CaseResult & { result_type: "case" })
  | (LegislationResult & { result_type: "legislation" });

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
  searchMode: string;
  timing: {
    embedding_ms: number;
    search_ms: number;
    total_ms: number;
  };
}
