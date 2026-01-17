"use client";

import { Calendar, Share2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AddToCollectionButton } from "@/components/collections";
import type { LegislationDetail } from "@/types";

interface LegislationHeaderProps {
  legislation: LegislationDetail;
}

export function LegislationHeader({
  legislation,
}: LegislationHeaderProps) {
  const handleShare = async () => {
    if (navigator.share) {
      await navigator.share({
        title: legislation.title_en,
        text: `Cap. ${legislation.chapter_number} - ${legislation.title_en}`,
        url: window.location.href,
      });
    } else {
      await navigator.clipboard.writeText(window.location.href);
    }
  };

  const getStatusVariant = (status: string) => {
    switch (status.toLowerCase()) {
      case "in force":
        return "default";
      case "repealed":
        return "destructive";
      case "not yet in force":
        return "secondary";
      default:
        return "outline";
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-lg font-semibold text-primary">
              Cap. {legislation.chapter_number}
            </span>
            <Badge variant={getStatusVariant(legislation.status)}>
              {legislation.status}
            </Badge>
            <Badge variant="outline">{legislation.type}</Badge>
          </div>
          <h1 className="text-2xl font-bold leading-tight lg:text-3xl">
            {legislation.title_en}
          </h1>
          {legislation.title_zh && (
            <p className="text-lg text-muted-foreground">
              {legislation.title_zh}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <AddToCollectionButton
            itemType="legislation"
            itemId={legislation.id}
            itemTitle={legislation.title_en}
          />
          <Button variant="outline" size="sm" onClick={handleShare}>
            <Share2 className="mr-2 h-4 w-4" />
            Share
          </Button>
          {legislation.source_url && (
            <a
              href={legislation.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" size="sm">
                <ExternalLink className="mr-2 h-4 w-4" />
                eLegislation
              </Button>
            </a>
          )}
        </div>
      </div>

      {legislation.commencement_date && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="h-4 w-4" />
          <span>
            Commenced:{" "}
            {new Date(legislation.commencement_date).toLocaleDateString(
              "en-GB",
              {
                day: "numeric",
                month: "long",
                year: "numeric",
              }
            )}
          </span>
        </div>
      )}
    </div>
  );
}
