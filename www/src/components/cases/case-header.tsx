"use client";

import { Calendar, Building, User, Share2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AddToCollectionButton } from "@/components/collections";
import type { CaseDetail } from "@/types";

interface CaseHeaderProps {
  caseData: CaseDetail;
}

export function CaseHeader({ caseData }: CaseHeaderProps) {
  const handleShare = async () => {
    if (navigator.share) {
      await navigator.share({
        title: caseData.case_name,
        text: `${caseData.neutral_citation} - ${caseData.case_name}`,
        url: window.location.href,
      });
    } else {
      await navigator.clipboard.writeText(window.location.href);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold leading-tight lg:text-3xl">
            {caseData.case_name}
          </h1>
          <p className="font-mono text-lg font-medium text-primary">
            {caseData.neutral_citation}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <AddToCollectionButton
            itemType="case"
            itemId={caseData.id}
            itemTitle={caseData.case_name}
          />
          <Button variant="outline" size="sm" onClick={handleShare}>
            <Share2 className="mr-2 h-4 w-4" />
            Share
          </Button>
          {caseData.pdf_url && (
            <a href={caseData.pdf_url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm">
                <Download className="mr-2 h-4 w-4" />
                PDF
              </Button>
            </a>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
        {caseData.court && (
          <span className="flex items-center gap-1.5">
            <Building className="h-4 w-4" />
            {caseData.court.name_en}
          </span>
        )}
        {caseData.decision_date && (
          <span className="flex items-center gap-1.5">
            <Calendar className="h-4 w-4" />
            {new Date(caseData.decision_date).toLocaleDateString("en-GB", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </span>
        )}
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
    </div>
  );
}
