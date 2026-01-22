"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getCaseDetail } from "@/lib/api/search";
import { CaseHeader, CaseContent, CaseMetadata } from "@/components/cases";
import type { CaseDetail } from "@/types";

function CaseDetailSkeleton() {
  return (
    <div className="container py-6">
      <Skeleton className="h-8 w-32 mb-6" />
      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-6">
          <div className="space-y-4">
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="h-6 w-48" />
            <div className="flex gap-4">
              <Skeleton className="h-6 w-32" />
              <Skeleton className="h-6 w-40" />
            </div>
          </div>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
        <div className="hidden lg:block">
          <Skeleton className="h-80 w-full" />
        </div>
      </div>
    </div>
  );
}

export default function CaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const handleBack = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push("/search?type=cases");
    }
  };

  const { data: caseData, isLoading, error } = useQuery<CaseDetail>({
    queryKey: ["case", id],
    queryFn: () => getCaseDetail(id),
    enabled: !!id,
    staleTime: 1000 * 60 * 60,
  });

  if (isLoading) {
    return <CaseDetailSkeleton />;
  }

  if (error) {
    return (
      <div className="container py-6">
        <Button variant="ghost" size="sm" className="mb-6" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to search
        </Button>
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
      <Button variant="ghost" size="sm" className="mb-6" onClick={handleBack}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to search
      </Button>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-6">
          <CaseHeader caseData={caseData} />
          <CaseContent caseData={caseData} />
        </div>
        <aside className="hidden lg:block">
          <div className="sticky top-20">
            <CaseMetadata caseData={caseData} />
          </div>
        </aside>
      </div>
    </div>
  );
}
