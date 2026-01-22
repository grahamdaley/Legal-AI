export type SearchType = "cases" | "legislation" | "all";
export type SearchMode = "semantic" | "hybrid" | "keyword";

export interface SearchFilters {
  court?: string;
  yearFrom?: number;
  yearTo?: number;
  legislationType?: string;
}

export interface SearchOptions {
  limit?: number;
  offset?: number;
  searchMode?: SearchMode;
  semanticWeight?: number;
}

export interface SearchRequest {
  query: string;
  type?: SearchType;
  filters?: SearchFilters;
  options?: SearchOptions;
}

export interface CaseResult {
  id: string;
  neutral_citation: string;
  case_name: string;
  court_id: string;
  court_name?: string;
  decision_date: string;
  headnote?: string;
  chunk_index?: number;
  chunk_text?: string;
  similarity_score?: number;
  fts_score?: number;
  combined_score?: number;
}

export interface LegislationResult {
  id: string;
  chapter_number: string;
  title_en: string;
  title_zh?: string;
  type: string;
  status: string;
  section_number?: string;
  section_title?: string;
  content_snippet?: string;
  chunk_index?: number;
  chunk_text?: string;
  similarity_score?: number;
  fts_score?: number;
  combined_score?: number;
}

export interface SearchResponse {
  results: (CaseResult | LegislationResult)[];
  query: string;
  searchMode: SearchMode;
  type: SearchType;
  total?: number;
  timing: {
    embedding_ms: number;
    search_ms: number;
    total_ms: number;
  };
}

export interface Suggestion {
  text: string;
  type: "citation" | "case_name" | "legislation" | "legal_term";
}

export interface SuggestionsResponse {
  suggestions: Suggestion[];
}

export interface CaseDetail {
  id: string;
  neutral_citation: string;
  case_number?: string;
  case_name: string;
  court: {
    id: string;
    name_en: string;
    code: string;
  };
  decision_date: string;
  judges?: string[];
  parties?: {
    applicants?: string[];
    respondents?: string[];
  };
  headnote?: string;
  full_text?: string;
  source_url?: string;
  pdf_url?: string;
}

export interface CitedCase {
  id: string | null;
  citation_text: string;
  cited_case_name: string | null;
  neutral_citation: string | null;
  case_name: string | null;
  court_code: string | null;
  decision_date: string | null;
  is_in_database: boolean;
}

export interface CitingCase {
  id: string;
  neutral_citation: string | null;
  case_name: string | null;
  court_code: string | null;
  decision_date: string | null;
}

export interface CitationsResponse {
  cited_cases: CitedCase[];
  citing_cases: CitingCase[];
}

export interface LegislationDetail {
  id: string;
  chapter_number: string;
  title_en: string;
  title_zh?: string;
  type: string;
  status: string;
  commencement_date?: string;
  source_url?: string;
  sections: LegislationSection[];
  schedules: LegislationSchedule[];
}

export interface LegislationSection {
  id: string;
  section_number: string;
  title?: string;
  content: string;
}

export interface LegislationSchedule {
  id: string;
  schedule_number: string;
  title?: string;
  content: string;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
  subscription_tier: "free" | "professional" | "enterprise";
  monthly_search_quota: number;
  searches_this_month: number;
  created_at: string;
}

export interface Collection {
  id: string;
  name: string;
  description?: string;
  is_public: boolean;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionItem {
  id: string;
  collection_id: string;
  item_type: "case" | "legislation";
  item_id: string;
  notes?: string;
  created_at: string;
  case?: CaseResult;
  legislation?: LegislationResult;
}
