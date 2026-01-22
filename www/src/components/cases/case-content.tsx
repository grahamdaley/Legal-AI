"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { FileText, BookOpen, Link2, ArrowUpRight, ArrowDownLeft, Loader2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getCaseCitations } from "@/lib/api/search";
import type { CaseDetail, CitedCase, CitingCase } from "@/types";

interface CaseContentProps {
  caseData: CaseDetail;
}

function OutgoingCitationCard({ citation }: { citation: CitedCase }) {
  // Display format: "Case Name [citation]" or just "[citation]" if no case name
  const displayText = citation.cited_case_name 
    ? `${citation.cited_case_name} ${citation.citation_text}`
    : citation.is_in_database && citation.case_name
      ? citation.case_name
      : citation.citation_text;

  const content = (
    <Card className={citation.is_in_database ? "hover:bg-accent/50 transition-colors cursor-pointer" : "opacity-75"}>
      <CardContent className="py-3 px-4">
        <div className="flex items-start gap-3">
          <ArrowUpRight className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium line-clamp-1">
              {displayText}
            </p>
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
              {citation.is_in_database ? (
                <>
                  {citation.neutral_citation && (
                    <span className="font-mono">{citation.neutral_citation}</span>
                  )}
                  {citation.court_code && (
                    <Badge variant="outline" className="text-xs">
                      {citation.court_code}
                    </Badge>
                  )}
                  {citation.decision_date && (
                    <span>
                      {new Date(citation.decision_date).toLocaleDateString("en-GB", {
                        year: "numeric",
                      })}
                    </span>
                  )}
                </>
              ) : (
                <Badge variant="secondary" className="text-xs">
                  Not in database
                </Badge>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (citation.is_in_database && citation.id) {
    return <Link href={`/cases/${citation.id}`}>{content}</Link>;
  }

  return content;
}

function IncomingCitationCard({ citation }: { citation: CitingCase }) {
  return (
    <Link href={`/cases/${citation.id}`}>
      <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
        <CardContent className="py-3 px-4">
          <div className="flex items-start gap-3">
            <ArrowDownLeft className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium line-clamp-1">
                {citation.case_name || "Untitled Case"}
              </p>
              <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                {citation.neutral_citation && (
                  <span className="font-mono">{citation.neutral_citation}</span>
                )}
                {citation.court_code && (
                  <Badge variant="outline" className="text-xs">
                    {citation.court_code}
                  </Badge>
                )}
                {citation.decision_date && (
                  <span>
                    {new Date(citation.decision_date).toLocaleDateString("en-GB", {
                      year: "numeric",
                    })}
                  </span>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export function CaseContent({ caseData }: CaseContentProps) {
  const [activeTab, setActiveTab] = useState("summary");

  const { data: citations, isLoading: citationsLoading } = useQuery({
    queryKey: ["citations", caseData.id],
    queryFn: () => getCaseCitations(caseData.id),
    enabled: activeTab === "citations",
    staleTime: 1000 * 60 * 60,
  });

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="summary" className="gap-2">
          <BookOpen className="h-4 w-4" />
          <span className="hidden sm:inline">Summary</span>
        </TabsTrigger>
        <TabsTrigger value="judgment" className="gap-2">
          <FileText className="h-4 w-4" />
          <span className="hidden sm:inline">Full Judgment</span>
        </TabsTrigger>
        <TabsTrigger value="citations" className="gap-2">
          <Link2 className="h-4 w-4" />
          <span className="hidden sm:inline">Citations</span>
        </TabsTrigger>
      </TabsList>

      <TabsContent value="summary" className="mt-4">
        <Card>
          <CardContent className="pt-6">
            {caseData.headnote ? (
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <p className="whitespace-pre-wrap leading-relaxed">
                  {caseData.headnote}
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                No AI-generated summary available for this case.
              </p>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="judgment" className="mt-4">
        <Card>
          <CardContent className="pt-6">
            {caseData.full_text ? (
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                  {caseData.full_text}
                </pre>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                Full judgment text is not available. Please view the original
                document on the Judiciary website.
              </p>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="citations" className="mt-4">
        {citationsLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                <ArrowUpRight className="h-4 w-4" />
                Cases Cited by This Judgment ({citations?.cited_cases?.length || 0})
              </h3>
              {citations?.cited_cases && citations.cited_cases.length > 0 ? (
                <div className="space-y-2">
                  {citations.cited_cases.map((citation, index) => (
                    <OutgoingCitationCard key={citation.id || `cited-${index}`} citation={citation} />
                  ))}
                </div>
              ) : (
                <Card>
                  <CardContent className="py-4">
                    <p className="text-sm text-muted-foreground italic">
                      No citations found in this judgment.
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>

            <div>
              <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                <ArrowDownLeft className="h-4 w-4" />
                Cases That Cite This Judgment ({citations?.citing_cases?.length || 0})
              </h3>
              {citations?.citing_cases && citations.citing_cases.length > 0 ? (
                <div className="space-y-2">
                  {citations.citing_cases.map((citation) => (
                    <IncomingCitationCard key={citation.id} citation={citation} />
                  ))}
                </div>
              ) : (
                <Card>
                  <CardContent className="py-4">
                    <p className="text-sm text-muted-foreground italic">
                      No cases citing this judgment found yet.
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        )}
      </TabsContent>
    </Tabs>
  );
}
