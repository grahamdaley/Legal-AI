import type {
  SearchRequest,
  SearchResponse,
  SuggestionsResponse,
  CaseDetail,
  LegislationDetail,
  CitationsResponse,
} from "@/types";
import { createClient } from "@/lib/supabase/client";

async function getAuthHeaders(): Promise<HeadersInit> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  
  if (!session?.access_token) {
    // Return empty headers if not authenticated - let the API return 401
    return {};
  }
  
  return {
    "Authorization": `Bearer ${session.access_token}`,
  };
}

export async function search(request: SearchRequest): Promise<SearchResponse> {
  const authHeaders = await getAuthHeaders();
  
  const response = await fetch("/api/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    try {
      const error = await response.json();
      throw new Error(error.error?.message || "Search failed");
    } catch (e) {
      if (e instanceof Error && e.message !== "Search failed") {
        throw e;
      }
      throw new Error(`Search failed with status ${response.status}`);
    }
  }

  return response.json();
}

export async function getSuggestions(
  query: string,
  type?: "cases" | "legislation" | "all"
): Promise<SuggestionsResponse> {
  const authHeaders = await getAuthHeaders();
  
  const params = new URLSearchParams({ q: query });
  if (type) {
    params.set("type", type);
  }

  const response = await fetch(`/api/suggestions?${params.toString()}`, {
    headers: authHeaders,
  });

  if (!response.ok) {
    try {
      const error = await response.json();
      throw new Error(error.error?.message || "Failed to get suggestions");
    } catch (e) {
      if (e instanceof Error && e.message !== "Failed to get suggestions") {
        throw e;
      }
      throw new Error(`Failed to get suggestions with status ${response.status}`);
    }
  }

  return response.json();
}

export async function getCaseDetail(id: string): Promise<CaseDetail> {
  const authHeaders = await getAuthHeaders();
  
  const response = await fetch(`/api/cases/${id}`, {
    headers: authHeaders,
  });

  if (!response.ok) {
    try {
      const error = await response.json();
      throw new Error(error.error?.message || "Failed to get case details");
    } catch (e) {
      if (e instanceof Error && e.message !== "Failed to get case details") {
        throw e;
      }
      throw new Error(`Failed to get case details with status ${response.status}`);
    }
  }

  return response.json();
}

export async function getLegislationDetail(
  id: string
): Promise<LegislationDetail> {
  const authHeaders = await getAuthHeaders();
  
  const response = await fetch(`/api/legislation/${id}`, {
    headers: authHeaders,
  });

  if (!response.ok) {
    try {
      const error = await response.json();
      throw new Error(error.error?.message || "Failed to get legislation details");
    } catch (e) {
      if (e instanceof Error && e.message !== "Failed to get legislation details") {
        throw e;
      }
      throw new Error(`Failed to get legislation details with status ${response.status}`);
    }
  }

  return response.json();
}

export async function getCaseCitations(id: string): Promise<CitationsResponse> {
  const authHeaders = await getAuthHeaders();
  
  const response = await fetch(`/api/cases/${id}/citations`, {
    headers: authHeaders,
  });

  if (!response.ok) {
    try {
      const error = await response.json();
      throw new Error(error.error?.message || "Failed to get case citations");
    } catch (e) {
      if (e instanceof Error && e.message !== "Failed to get case citations") {
        throw e;
      }
      throw new Error(`Failed to get case citations with status ${response.status}`);
    }
  }

  return response.json();
}
