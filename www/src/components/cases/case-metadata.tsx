"use client";

import { ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { CaseDetail } from "@/types";

interface CaseMetadataProps {
  caseData: CaseDetail;
}

export function CaseMetadata({ caseData }: CaseMetadataProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Case Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {caseData.case_number && (
          <div>
            <dt className="font-medium text-muted-foreground">Case Number</dt>
            <dd className="mt-1">{caseData.case_number}</dd>
          </div>
        )}

        {caseData.court && (
          <div>
            <dt className="font-medium text-muted-foreground">Court</dt>
            <dd className="mt-1">{caseData.court.name_en}</dd>
            <dd className="text-xs text-muted-foreground">
              ({caseData.court.code})
            </dd>
          </div>
        )}

        {caseData.decision_date && (
          <div>
            <dt className="font-medium text-muted-foreground">Decision Date</dt>
            <dd className="mt-1">
              {new Date(caseData.decision_date).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </dd>
          </div>
        )}

        {caseData.parties && (
          <div>
            <dt className="font-medium text-muted-foreground">Parties</dt>
            <dd className="mt-1 space-y-2">
              {caseData.parties.applicants &&
                caseData.parties.applicants.length > 0 && (
                  <div>
                    <span className="text-xs text-muted-foreground">
                      Applicant(s):
                    </span>
                    <p>{caseData.parties.applicants.join(", ")}</p>
                  </div>
                )}
              {caseData.parties.respondents &&
                caseData.parties.respondents.length > 0 && (
                  <div>
                    <span className="text-xs text-muted-foreground">
                      Respondent(s):
                    </span>
                    <p>{caseData.parties.respondents.join(", ")}</p>
                  </div>
                )}
            </dd>
          </div>
        )}

        {caseData.judges && caseData.judges.length > 0 && (
          <div>
            <dt className="font-medium text-muted-foreground">Judges</dt>
            <dd className="mt-1">
              <ul className="list-inside list-disc">
                {caseData.judges.map((judge, i) => (
                  <li key={i}>{judge}</li>
                ))}
              </ul>
            </dd>
          </div>
        )}

        {caseData.source_url && (
          <div className="pt-2">
            <a
              href={caseData.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" size="sm" className="w-full">
                <ExternalLink className="mr-2 h-4 w-4" />
                View on Judiciary
              </Button>
            </a>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
