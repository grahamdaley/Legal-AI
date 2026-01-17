"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Filter, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import type { SearchFilters, SearchType } from "@/types";

const COURTS = [
  { code: "CFA", name: "Court of Final Appeal" },
  { code: "CA", name: "Court of Appeal" },
  { code: "CFI", name: "Court of First Instance" },
  { code: "DC", name: "District Court" },
  { code: "FC", name: "Family Court" },
  { code: "LT", name: "Lands Tribunal" },
  { code: "CT", name: "Competition Tribunal" },
];

const LEGISLATION_TYPES = [
  { value: "ordinance", label: "Ordinance" },
  { value: "regulation", label: "Regulation" },
  { value: "rule", label: "Rule" },
  { value: "order", label: "Order" },
];

interface SearchFiltersProps {
  filters: SearchFilters;
  searchType: SearchType;
  onFiltersChange: (filters: SearchFilters) => void;
}

export function SearchFiltersComponent({
  filters,
  searchType,
  onFiltersChange,
}: SearchFiltersProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const updateFilters = (newFilters: SearchFilters) => {
    onFiltersChange(newFilters);
    const params = new URLSearchParams(searchParams.toString());
    
    if (newFilters.court) {
      params.set("court", newFilters.court);
    } else {
      params.delete("court");
    }
    
    if (newFilters.yearFrom) {
      params.set("yearFrom", newFilters.yearFrom.toString());
    } else {
      params.delete("yearFrom");
    }
    
    if (newFilters.yearTo) {
      params.set("yearTo", newFilters.yearTo.toString());
    } else {
      params.delete("yearTo");
    }
    
    if (newFilters.legislationType) {
      params.set("legislationType", newFilters.legislationType);
    } else {
      params.delete("legislationType");
    }
    
    router.push(`/search?${params.toString()}`);
  };

  const clearFilters = () => {
    updateFilters({});
  };

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="h-8">
            <Filter className="mr-2 h-4 w-4" />
            Filters
            {activeFilterCount > 0 && (
              <Badge variant="secondary" className="ml-2">
                {activeFilterCount}
              </Badge>
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          {(searchType === "cases" || searchType === "all") && (
            <>
              <DropdownMenuLabel>Court</DropdownMenuLabel>
              {COURTS.map((court) => (
                <DropdownMenuCheckboxItem
                  key={court.code}
                  checked={filters.court === court.code}
                  onCheckedChange={(checked) =>
                    updateFilters({
                      ...filters,
                      court: checked ? court.code : undefined,
                    })
                  }
                >
                  {court.name}
                </DropdownMenuCheckboxItem>
              ))}
              <DropdownMenuSeparator />
            </>
          )}

          {(searchType === "legislation" || searchType === "all") && (
            <>
              <DropdownMenuLabel>Legislation Type</DropdownMenuLabel>
              {LEGISLATION_TYPES.map((type) => (
                <DropdownMenuCheckboxItem
                  key={type.value}
                  checked={filters.legislationType === type.value}
                  onCheckedChange={(checked) =>
                    updateFilters({
                      ...filters,
                      legislationType: checked ? type.value : undefined,
                    })
                  }
                >
                  {type.label}
                </DropdownMenuCheckboxItem>
              ))}
              <DropdownMenuSeparator />
            </>
          )}

          <DropdownMenuLabel>Year Range</DropdownMenuLabel>
          <div className="px-2 py-1.5 flex items-center gap-2">
            <Input
              type="number"
              placeholder="From"
              value={filters.yearFrom || ""}
              onChange={(e) =>
                updateFilters({
                  ...filters,
                  yearFrom: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              className="h-8 w-20"
              min={1900}
              max={new Date().getFullYear()}
            />
            <span className="text-muted-foreground">-</span>
            <Input
              type="number"
              placeholder="To"
              value={filters.yearTo || ""}
              onChange={(e) =>
                updateFilters({
                  ...filters,
                  yearTo: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              className="h-8 w-20"
              min={1900}
              max={new Date().getFullYear()}
            />
          </div>
        </DropdownMenuContent>
      </DropdownMenu>

      {activeFilterCount > 0 && (
        <>
          {filters.court && (
            <Badge variant="secondary" className="h-8 gap-1">
              Court: {filters.court}
              <button
                onClick={() => updateFilters({ ...filters, court: undefined })}
                className="ml-1 hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}
          {filters.legislationType && (
            <Badge variant="secondary" className="h-8 gap-1">
              Type: {filters.legislationType}
              <button
                onClick={() =>
                  updateFilters({ ...filters, legislationType: undefined })
                }
                className="ml-1 hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}
          {(filters.yearFrom || filters.yearTo) && (
            <Badge variant="secondary" className="h-8 gap-1">
              Year: {filters.yearFrom || "..."} - {filters.yearTo || "..."}
              <button
                onClick={() =>
                  updateFilters({
                    ...filters,
                    yearFrom: undefined,
                    yearTo: undefined,
                  })
                }
                className="ml-1 hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-muted-foreground"
            onClick={clearFilters}
          >
            Clear all
          </Button>
        </>
      )}
    </div>
  );
}
