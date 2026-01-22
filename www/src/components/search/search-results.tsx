"use client";

import Link from "next/link";
import { FileText, Scale, Calendar, Building, Quote } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { CaseResult, LegislationResult, SearchType } from "@/types";

interface SearchResultsProps {
  results: (CaseResult | LegislationResult)[];
  searchType: SearchType;
  isLoading?: boolean;
  query?: string;
}

function isCaseResult(
  result: CaseResult | LegislationResult
): result is CaseResult {
  return "neutral_citation" in result;
}

function CaseResultCard({ result }: { result: CaseResult }) {
  return (
    <Link href={`/cases/${result.id}`}>
      <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <CardTitle className="text-base font-medium line-clamp-2">
                {result.case_name}
              </CardTitle>
            </div>
            {result.similarity_score !== undefined && (
              <Badge variant="outline" className="flex-shrink-0">
                {Math.round(result.similarity_score * 100)}% match
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground mb-2">
            <span className="font-mono">{result.neutral_citation}</span>
            {result.court_name && (
              <span className="flex items-center gap-1">
                <Building className="h-3 w-3" />
                {result.court_name}
              </span>
            )}
            {result.decision_date && (
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {new Date(result.decision_date).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </span>
            )}
          </div>
          {result.chunk_text ? (
            <div className="mt-2 p-2 bg-muted/50 rounded-md border-l-2 border-primary/50">
              <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                <Quote className="h-3 w-3" />
                <span>Matched passage</span>
              </div>
              <p className="text-sm text-foreground/80 line-clamp-3 italic">
                &ldquo;{result.chunk_text}&rdquo;
              </p>
            </div>
          ) : result.headnote ? (
            <p className="text-sm text-muted-foreground line-clamp-3 mt-2">
              {result.headnote}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </Link>
  );
}

function LegislationResultCard({ result }: { result: LegislationResult }) {
  return (
    <Link href={`/legislation/${result.id}`}>
      <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <CardTitle className="text-base font-medium line-clamp-2">
                {result.title_en}
              </CardTitle>
            </div>
            {result.similarity_score !== undefined && (
              <Badge variant="outline" className="flex-shrink-0">
                {Math.round(result.similarity_score * 100)}% match
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="font-mono">Cap. {result.chapter_number}</span>
            <Badge variant="secondary" className="capitalize">
              {result.type}
            </Badge>
            <Badge
              variant={result.status === "current" ? "default" : "secondary"}
              className="capitalize"
            >
              {result.status}
            </Badge>
          </div>
          {result.chunk_text ? (
            <div className="mt-2 p-2 bg-muted/50 rounded-md border-l-2 border-primary/50">
              <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                <Quote className="h-3 w-3" />
                <span>
                  Matched passage
                  {result.section_number && ` (§${result.section_number})`}
                </span>
              </div>
              <p className="text-sm text-foreground/80 line-clamp-3 italic">
                &ldquo;{result.chunk_text}&rdquo;
              </p>
            </div>
          ) : result.title_zh ? (
            <p className="text-sm text-muted-foreground mt-2">
              {result.title_zh}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </Link>
  );
}

function ResultSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-5 w-3/4" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex gap-4 mb-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-20" />
        </div>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6 mt-1" />
      </CardContent>
    </Card>
  );
}

export function SearchResults({
  results,
  searchType,
  isLoading,
  query,
}: SearchResultsProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <ResultSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          {query
            ? `No results found for "${query}"`
            : "Enter a search query to find cases and legislation"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((result) =>
        isCaseResult(result) ? (
          <CaseResultCard key={result.id} result={result} />
        ) : (
          <LegislationResultCard key={result.id} result={result} />
        )
      )}
    </div>
  );
}
