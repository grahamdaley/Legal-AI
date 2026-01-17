"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Calendar, ExternalLink, BookOpen } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getLegislationDetail } from "@/lib/api/search";
import type { LegislationDetail } from "@/types";

export default function LegislationDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const { data: legislation, isLoading, error } = useQuery<LegislationDetail>({
    queryKey: ["legislation", id],
    queryFn: () => getLegislationDetail(id),
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
          <p className="font-medium">Failed to load legislation</p>
          <p className="text-sm">{(error as Error).message}</p>
        </div>
      </div>
    );
  }

  if (!legislation) {
    return null;
  }

  return (
    <div className="container py-6">
      <Link href="/search?type=legislation">
        <Button variant="ghost" size="sm" className="mb-6">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to search
        </Button>
      </Link>

      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <BookOpen className="h-6 w-6 text-muted-foreground" />
            <span className="font-mono text-lg">Cap. {legislation.chapter_number}</span>
          </div>
          <h1 className="text-2xl font-bold mb-2">{legislation.title_en}</h1>
          {legislation.title_zh && (
            <p className="text-lg text-muted-foreground">{legislation.title_zh}</p>
          )}
          <div className="flex flex-wrap items-center gap-2 mt-4">
            <Badge variant="secondary" className="capitalize">
              {legislation.type}
            </Badge>
            <Badge
              variant={legislation.status === "current" ? "default" : "secondary"}
              className="capitalize"
            >
              {legislation.status}
            </Badge>
            {legislation.commencement_date && (
              <span className="flex items-center gap-1 text-sm text-muted-foreground">
                <Calendar className="h-4 w-4" />
                Commenced:{" "}
                {new Date(legislation.commencement_date).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })}
              </span>
            )}
          </div>
        </div>

        <Tabs defaultValue="sections">
          <TabsList>
            <TabsTrigger value="sections">
              Sections ({legislation.sections?.length || 0})
            </TabsTrigger>
            <TabsTrigger value="schedules">
              Schedules ({legislation.schedules?.length || 0})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="sections" className="mt-4">
            {legislation.sections && legislation.sections.length > 0 ? (
              <div className="space-y-4">
                {legislation.sections.map((section) => (
                  <Card key={section.id}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <span className="font-mono text-muted-foreground">
                          s.{section.section_number}
                        </span>
                        {section.title && <span>{section.title}</span>}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="prose prose-sm max-w-none dark:prose-invert">
                        <pre className="whitespace-pre-wrap text-sm font-sans">
                          {section.content}
                        </pre>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-8">
                No sections available
              </p>
            )}
          </TabsContent>

          <TabsContent value="schedules" className="mt-4">
            {legislation.schedules && legislation.schedules.length > 0 ? (
              <div className="space-y-4">
                {legislation.schedules.map((schedule) => (
                  <Card key={schedule.id}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <span className="font-mono text-muted-foreground">
                          Schedule {schedule.schedule_number}
                        </span>
                        {schedule.title && <span>{schedule.title}</span>}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="prose prose-sm max-w-none dark:prose-invert">
                        <pre className="whitespace-pre-wrap text-sm font-sans">
                          {schedule.content}
                        </pre>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-8">
                No schedules available
              </p>
            )}
          </TabsContent>
        </Tabs>

        {legislation.source_url && (
          <div>
            <a href={legislation.source_url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm">
                <ExternalLink className="mr-2 h-4 w-4" />
                View on eLegislation
              </Button>
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
