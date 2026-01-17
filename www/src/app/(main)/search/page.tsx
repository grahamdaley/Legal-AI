"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useMemo, Suspense } from "react";
import {
  SearchBar,
  SearchResults,
  SearchFiltersComponent,
  SearchTypeTabs,
} from "@/components/search";
import { search } from "@/lib/api/search";
import type { SearchFilters, SearchType, SearchResponse } from "@/types";

function SearchPageContent() {
  const searchParams = useSearchParams();
  const queryParam = searchParams.get("q") || "";
  const typeParam = (searchParams.get("type") as SearchType) || "all";
  const courtParam = searchParams.get("court") || undefined;
  const yearFromParam = searchParams.get("yearFrom");
  const yearToParam = searchParams.get("yearTo");
  const legislationTypeParam = searchParams.get("legislationType") || undefined;

  const searchType = typeParam;
  const filters = useMemo<SearchFilters>(
    () => ({
      court: courtParam,
      yearFrom: yearFromParam ? parseInt(yearFromParam) : undefined,
      yearTo: yearToParam ? parseInt(yearToParam) : undefined,
      legislationType: legislationTypeParam,
    }),
    [courtParam, yearFromParam, yearToParam, legislationTypeParam]
  );

  const { data, isLoading, error } = useQuery<SearchResponse>({
    queryKey: ["search", queryParam, searchType, filters],
    queryFn: () =>
      search({
        query: queryParam,
        type: searchType,
        filters,
        options: {
          limit: 20,
          searchMode: "hybrid",
        },
      }),
    enabled: !!queryParam,
  });

  return (
    <div className="container py-6">
      <div className="mb-6">
        <SearchBar defaultValue={queryParam} />
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-6">
        <SearchTypeTabs value={searchType} />
        <SearchFiltersComponent
          filters={filters}
          searchType={searchType}
          onFiltersChange={() => {}}
        />
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-4 text-destructive mb-6">
          <p className="text-sm font-medium">Search failed</p>
          <p className="text-sm">{(error as Error).message}</p>
        </div>
      )}

      {data && (
        <div className="mb-4 text-sm text-muted-foreground">
          Found {data.results.length} results in {data.timing.total_ms}ms
        </div>
      )}

      <SearchResults
        results={data?.results || []}
        searchType={searchType}
        isLoading={isLoading && !!queryParam}
        query={queryParam}
      />
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="container py-6">Loading...</div>}>
      <SearchPageContent />
    </Suspense>
  );
}
