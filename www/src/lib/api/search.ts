import type {
  SearchRequest,
  SearchResponse,
  SuggestionsResponse,
  CaseDetail,
  LegislationDetail,
} from "@/types";

export async function search(request: SearchRequest): Promise<SearchResponse> {
  const response = await fetch("/api/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Search failed");
  }

  return response.json();
}

export async function getSuggestions(
  query: string,
  type?: "cases" | "legislation" | "all"
): Promise<SuggestionsResponse> {
  const params = new URLSearchParams({ q: query });
  if (type) {
    params.set("type", type);
  }

  const response = await fetch(`/api/suggestions?${params.toString()}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to get suggestions");
  }

  return response.json();
}

export async function getCaseDetail(id: string): Promise<CaseDetail> {
  const response = await fetch(`/api/cases/${id}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to get case details");
  }

  return response.json();
}

export async function getLegislationDetail(
  id: string
): Promise<LegislationDetail> {
  const response = await fetch(`/api/legislation/${id}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to get legislation details");
  }

  return response.json();
}
