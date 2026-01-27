"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  search,
  getSuggestions,
  getCaseDetail,
  getLegislationDetail,
  getCaseCitations,
} from "@/lib/api/search";
import type {
  SearchRequest,
  SuggestionsResponse,
  CaseDetail,
  LegislationDetail,
  CitationsResponse,
} from "@/types";

const STALE_TIME = 5 * 60 * 1000; // 5 minutes
const CACHE_TIME = 30 * 60 * 1000; // 30 minutes

/**
 * Hook for performing searches with caching.
 * Uses mutation since search requests have a body.
 */
export function useSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SearchRequest) => search(request),
    onSuccess: (data, variables) => {
      // Cache the search results
      queryClient.setQueryData(
        ["search", JSON.stringify(variables)],
        data
      );
    },
  });
}

/**
 * Hook for fetching search suggestions with caching.
 */
export function useSuggestions(
  query: string,
  type?: "cases" | "legislation" | "all",
  enabled = true
) {
  return useQuery<SuggestionsResponse>({
    queryKey: ["suggestions", query, type],
    queryFn: () => getSuggestions(query, type),
    enabled: enabled && query.length >= 2,
    staleTime: STALE_TIME,
    gcTime: CACHE_TIME,
  });
}

/**
 * Hook for fetching case details with caching.
 */
export function useCaseDetail(id: string, enabled = true) {
  return useQuery<CaseDetail>({
    queryKey: ["case", id],
    queryFn: () => getCaseDetail(id),
    enabled: enabled && !!id,
    staleTime: STALE_TIME,
    gcTime: CACHE_TIME,
  });
}

/**
 * Hook for fetching legislation details with caching.
 */
export function useLegislationDetail(id: string, enabled = true) {
  return useQuery<LegislationDetail>({
    queryKey: ["legislation", id],
    queryFn: () => getLegislationDetail(id),
    enabled: enabled && !!id,
    staleTime: STALE_TIME,
    gcTime: CACHE_TIME,
  });
}

/**
 * Hook for fetching case citations with caching.
 */
export function useCaseCitations(id: string, enabled = true) {
  return useQuery<CitationsResponse>({
    queryKey: ["citations", id],
    queryFn: () => getCaseCitations(id),
    enabled: enabled && !!id,
    staleTime: STALE_TIME,
    gcTime: CACHE_TIME,
  });
}

/**
 * Hook for prefetching case details (useful for hover previews).
 */
export function usePrefetchCase() {
  const queryClient = useQueryClient();

  return (id: string) => {
    queryClient.prefetchQuery({
      queryKey: ["case", id],
      queryFn: () => getCaseDetail(id),
      staleTime: STALE_TIME,
    });
  };
}

/**
 * Hook for prefetching legislation details.
 */
export function usePrefetchLegislation() {
  const queryClient = useQueryClient();

  return (id: string) => {
    queryClient.prefetchQuery({
      queryKey: ["legislation", id],
      queryFn: () => getLegislationDetail(id),
      staleTime: STALE_TIME,
    });
  };
}
