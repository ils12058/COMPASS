"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Select } from "@/components/ui/select";
import { resourceCategoryLabels, resourceKindLabels } from "@/features/public/shared/presentation";
import {
  ResourceCategoryValue,
  ResourceKindValue,
  type ResourceCategoryValue as ResourceCategory,
  type ResourceKindValue as ResourceKind,
} from "@/lib/api/generated/model";

export function ResourceFilters({ category, kind }: { category?: ResourceCategory; kind?: ResourceKind }) {
  const router = useRouter();
  const pathname = usePathname();
  const currentParams = useSearchParams();

  function updateFilter(name: "category" | "kind", value: string) {
    const params = new URLSearchParams(currentParams.toString());
    if (value) params.set(name, value);
    else params.delete(name);
    params.delete("page");
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  // Two selects and nothing to type, so each choice applies as soon as it changes.
  return (
    <FilterToolbar fieldsClassName="sm:grid-cols-2 lg:grid-cols-[repeat(2,minmax(0,16rem))]">
      <FilterField label="Category" htmlFor="resource-filter-category">
        <Select
          id="resource-filter-category"
          value={category ?? ""}
          onChange={(event) => updateFilter("category", event.target.value)}
        >
          <option value="">All categories</option>
          {Object.values(ResourceCategoryValue).map((value) => (
            <option key={value} value={value}>{resourceCategoryLabels[value]}</option>
          ))}
        </Select>
      </FilterField>
      <FilterField label="Resource type" htmlFor="resource-filter-kind">
        <Select
          id="resource-filter-kind"
          value={kind ?? ""}
          onChange={(event) => updateFilter("kind", event.target.value)}
        >
          <option value="">All resource types</option>
          {Object.values(ResourceKindValue).map((value) => (
            <option key={value} value={value}>{resourceKindLabels[value]}</option>
          ))}
        </Select>
      </FilterField>
    </FilterToolbar>
  );
}
