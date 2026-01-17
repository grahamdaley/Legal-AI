"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { SearchType } from "@/types";

interface SearchTypeTabsProps {
  value: SearchType;
  onChange?: (value: SearchType) => void;
}

export function SearchTypeTabs({ value, onChange }: SearchTypeTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleChange = (newValue: string) => {
    const searchType = newValue as SearchType;
    if (onChange) {
      onChange(searchType);
    } else {
      const params = new URLSearchParams(searchParams.toString());
      params.set("type", searchType);
      router.push(`/search?${params.toString()}`);
    }
  };

  return (
    <Tabs value={value} onValueChange={handleChange}>
      <TabsList>
        <TabsTrigger value="all">All</TabsTrigger>
        <TabsTrigger value="cases">Cases</TabsTrigger>
        <TabsTrigger value="legislation">Legislation</TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
