"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { LegislationSchedule } from "@/types";

interface SchedulesListProps {
  schedules: LegislationSchedule[];
}

export function SchedulesList({ schedules }: SchedulesListProps) {
  const [expandedSchedules, setExpandedSchedules] = useState<Set<string>>(
    new Set()
  );

  const toggleSchedule = (id: string) => {
    setExpandedSchedules((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (schedules.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold">Schedules</h3>
      {schedules.map((schedule) => (
        <Collapsible
          key={schedule.id}
          open={expandedSchedules.has(schedule.id)}
          onOpenChange={() => toggleSchedule(schedule.id)}
        >
          <Card>
            <CollapsibleTrigger asChild>
              <button className="flex w-full items-center gap-3 p-4 text-left hover:bg-muted/50">
                {expandedSchedules.has(schedule.id) ? (
                  <ChevronDown className="h-4 w-4 flex-shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 flex-shrink-0" />
                )}
                <span className="font-mono text-sm font-medium text-primary">
                  Schedule {schedule.schedule_number}
                </span>
                {schedule.title && (
                  <span className="text-sm">{schedule.title}</span>
                )}
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent className="border-t pt-4">
                <div className="prose prose-sm max-w-none dark:prose-invert">
                  <pre className="whitespace-pre-wrap font-sans text-sm">
                    {schedule.content}
                  </pre>
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      ))}
    </div>
  );
}
