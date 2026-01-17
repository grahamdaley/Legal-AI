"use client";

import { useState } from "react";
import { List, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { LegislationSection, LegislationSchedule } from "@/types";

interface TableOfContentsProps {
  sections: LegislationSection[];
  schedules: LegislationSchedule[];
  onNavigate: (id: string) => void;
}

export function TableOfContents({
  sections,
  schedules,
  onNavigate,
}: TableOfContentsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <List className="h-4 w-4" />
            Table of Contents
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="lg:hidden"
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent
        className={`${isExpanded ? "block" : "hidden"} lg:block`}
      >
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-4">
            {sections.length > 0 && (
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                  Sections
                </h4>
                <ul className="space-y-1">
                  {sections.map((section) => (
                    <li key={section.id}>
                      <button
                        onClick={() => onNavigate(section.id)}
                        className="w-full text-left text-sm hover:text-primary hover:underline"
                      >
                        <span className="font-mono text-xs">
                          {section.section_number}
                        </span>
                        {section.title && (
                          <span className="ml-2 text-muted-foreground">
                            {section.title}
                          </span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {schedules.length > 0 && (
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                  Schedules
                </h4>
                <ul className="space-y-1">
                  {schedules.map((schedule) => (
                    <li key={schedule.id}>
                      <button
                        onClick={() => onNavigate(schedule.id)}
                        className="w-full text-left text-sm hover:text-primary hover:underline"
                      >
                        <span className="font-mono text-xs">
                          Schedule {schedule.schedule_number}
                        </span>
                        {schedule.title && (
                          <span className="ml-2 text-muted-foreground">
                            {schedule.title}
                          </span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
