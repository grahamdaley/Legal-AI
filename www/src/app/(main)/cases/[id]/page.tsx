"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Calendar, Building, User, ExternalLink, FileText } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { getCaseDetail } from "@/lib/api/search";
import type { CaseDetail } from "@/types";

export default function CaseDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const { data: caseData, isLoading, error } = useQuery<CaseDetail>({
    queryKey: ["case", id],
    queryFn: () => getCaseDetail(id),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="container py-6">
        <Skeleton className="h-8 w-32 mb-6" />
        <Skeleton className="h-10 w-3/4 mb-4" />
        <div className="flex gap-4 mb-6">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-6 w-28" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container py-6">
        <Link href="/search">
          <Button variant="ghost" size="sm" className="mb-6">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to search
          </Button>
        </Link>
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">Failed to load case</p>
          <p className="text-sm">{(error as Error).message}</p>
        </div>
      </div>
    );
  }

  if (!caseData) {
    return null;
  }

  return (
    <div className="container py-6">
      <Link href="/search?type=cases">
        <Button variant="ghost" size="sm" className="mb-6">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to search
        </Button>
      </Link>

      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold mb-2">{caseData.case_name}</h1>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
            <span className="font-mono font-medium text-foreground">
              {caseData.neutral_citation}
            </span>
            {caseData.court && (
              <span className="flex items-center gap-1">
                <Building className="h-4 w-4" />
                {caseData.court.name_en}
              </span>
            )}
            {caseData.decision_date && (
              <span className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                {new Date(caseData.decision_date).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })}
              </span>
            )}
          </div>
        </div>

        {caseData.judges && caseData.judges.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Judges:</span>
            {caseData.judges.map((judge, i) => (
              <Badge key={i} variant="secondary">
                {judge}
              </Badge>
            ))}
          </div>
        )}

        {caseData.parties && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Parties</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              {caseData.parties.applicants && caseData.parties.applicants.length > 0 && (
                <div className="mb-2">
                  <span className="font-medium">Applicant(s): </span>
                  {caseData.parties.applicants.join(", ")}
                </div>
              )}
              {caseData.parties.respondents && caseData.parties.respondents.length > 0 && (
                <div>
                  <span className="font-medium">Respondent(s): </span>
                  {caseData.parties.respondents.join(", ")}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {caseData.headnote && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Headnote</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm whitespace-pre-wrap">{caseData.headnote}</p>
            </CardContent>
          </Card>
        )}

        {caseData.full_text && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Full Judgment
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <pre className="whitespace-pre-wrap text-sm font-sans">
                  {caseData.full_text}
                </pre>
              </div>
            </CardContent>
          </Card>
        )}

        {(caseData.source_url || caseData.pdf_url) && (
          <div className="flex gap-4">
            {caseData.source_url && (
              <a href={caseData.source_url} target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  View on Judiciary
                </Button>
              </a>
            )}
            {caseData.pdf_url && (
              <a href={caseData.pdf_url} target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm">
                  <FileText className="mr-2 h-4 w-4" />
                  Download PDF
                </Button>
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
