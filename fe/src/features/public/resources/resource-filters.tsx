"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { resourceCategoryLabels, resourceKindLabels } from "@/features/public/shared/presentation";
import {
  ResourceCategoryValue,
  ResourceKindValue,
  type ResourceCategoryValue as ResourceCategory,
  type ResourceKindValue as ResourceKind,
  type ResourceOrdering,
} from "@/lib/api/generated/model";

// The canonical list URL for submitted filters: every applied filter together, a trimmed search,
// and no page, so a new set of filters starts on page 1.
// A chosen order is kept; sorting is not a filter.
export function resourceFiltersHref(values: {
  search: string;
  category: string;
  kind: string;
  ordering?: ResourceOrdering;
  page?: number;
}): string {
  const params = new URLSearchParams();
  const term = values.search.trim();
  if (term) params.set("search", term);
  if (values.category) params.set("category", values.category);
  if (values.kind) params.set("kind", values.kind);
  if (values.ordering) params.set("ordering", values.ordering);
  if (values.page !== undefined) params.set("page", String(values.page));
  return params.size ? `/resources?${params.toString()}` : "/resources";
}

export function ResourceFilters({
  search,
  category,
  kind,
  ordering,
}: {
  search?: string;
  category?: ResourceCategory;
  kind?: ResourceKind;
  ordering?: ResourceOrdering;
}) {
  const router = useRouter();
  const filtered = Boolean(search || category || kind);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    router.push(resourceFiltersHref({
      search: String(form.get("search") ?? ""),
      category: String(form.get("category") ?? ""),
      kind: String(form.get("kind") ?? ""),
      ordering,
    }));
  }

  return (
    <form role="search" aria-label="Search resources" onSubmit={submit} key={`${search ?? ""}:${category ?? ""}:${kind ?? ""}`}>
      <FilterToolbar
        fieldsClassName="lg:grid-cols-[minmax(0,1fr)_repeat(2,minmax(0,13rem))]"
        actions={<>
          {filtered ? <Link href={resourceFiltersHref({ search: "", category: "", kind: "", ordering })} className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : null}
          <Button type="submit">Apply filters</Button>
        </>}
      >
        <FilterField label="Search resources" htmlFor="resource-filter-search">
          <Input id="resource-filter-search" name="search" type="search" placeholder="Search resources" defaultValue={search} />
        </FilterField>
        <FilterField label="Category" htmlFor="resource-filter-category">
          <Select id="resource-filter-category" name="category" defaultValue={category ?? ""}>
            <option value="">All categories</option>
            {Object.values(ResourceCategoryValue).map((value) => (
              <option key={value} value={value}>{resourceCategoryLabels[value]}</option>
            ))}
          </Select>
        </FilterField>
        <FilterField label="Resource type" htmlFor="resource-filter-kind">
          <Select id="resource-filter-kind" name="kind" defaultValue={kind ?? ""}>
            <option value="">All resource types</option>
            {Object.values(ResourceKindValue).map((value) => (
              <option key={value} value={value}>{resourceKindLabels[value]}</option>
            ))}
          </Select>
        </FilterField>
      </FilterToolbar>
    </form>
  );
}
