"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getLegislationDetail } from "@/lib/api/search";
import {
  LegislationHeader,
  SectionsList,
  SchedulesList,
  TableOfContents,
} from "@/components/legislation";
import type { LegislationDetail } from "@/types";

function LegislationDetailSkeleton() {
  return (
    <div className="container py-6">
      <Skeleton className="h-8 w-32 mb-6" />
      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <div className="space-y-6">
          <div className="space-y-4">
            <div className="flex gap-2">
              <Skeleton className="h-6 w-24" />
              <Skeleton className="h-6 w-20" />
              <Skeleton className="h-6 w-20" />
            </div>
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="h-6 w-1/2" />
          </div>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
        <div className="hidden lg:block">
          <Skeleton className="h-96 w-full" />
        </div>
      </div>
    </div>
  );
}

export default function LegislationDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const { data: legislation, isLoading, error } = useQuery<LegislationDetail>({
    queryKey: ["legislation", id],
    queryFn: () => getLegislationDetail(id),
    enabled: !!id,
    staleTime: 1000 * 60 * 60,
  });

  if (isLoading) {
    return <LegislationDetailSkeleton />;
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

  const handleNavigate = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <div className="container py-6">
      <Link href="/search?type=legislation">
        <Button variant="ghost" size="sm" className="mb-6">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to search
        </Button>
      </Link>

      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <div className="space-y-6">
          <LegislationHeader legislation={legislation} />

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
                <SectionsList sections={legislation.sections} />
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  No sections available
                </p>
              )}
            </TabsContent>

            <TabsContent value="schedules" className="mt-4">
              {legislation.schedules && legislation.schedules.length > 0 ? (
                <SchedulesList schedules={legislation.schedules} />
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  No schedules available
                </p>
              )}
            </TabsContent>
          </Tabs>
        </div>

        <aside className="hidden lg:block">
          <div className="sticky top-20">
            <TableOfContents
              sections={legislation.sections || []}
              schedules={legislation.schedules || []}
              onNavigate={handleNavigate}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
