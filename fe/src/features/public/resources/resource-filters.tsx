"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

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

  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end">
      <label className="grid gap-1.5 text-xs font-semibold text-muted sm:w-60">
        Category
        <Select
          value={category ?? ""}
          onChange={(event) => updateFilter("category", event.target.value)}
          className="font-normal"
        >
          <option value="">All categories</option>
          {Object.values(ResourceCategoryValue).map((value) => (
            <option key={value} value={value}>{resourceCategoryLabels[value]}</option>
          ))}
        </Select>
      </label>
      <label className="grid gap-1.5 text-xs font-semibold text-muted sm:w-60">
        Resource type
        <Select
          value={kind ?? ""}
          onChange={(event) => updateFilter("kind", event.target.value)}
          className="font-normal"
        >
          <option value="">All resource types</option>
          {Object.values(ResourceKindValue).map((value) => (
            <option key={value} value={value}>{resourceKindLabels[value]}</option>
          ))}
        </Select>
      </label>
    </div>
  );
}
