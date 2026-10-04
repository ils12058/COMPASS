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
} from "@/lib/api/generated/model";

// The canonical list URL for submitted filters: every applied filter together, a trimmed search,
// and no page, so a new set of filters starts on page 1.
export function resourceFiltersHref(values: { search: string; category: string; kind: string }): string {
  const params = new URLSearchParams();
  const term = values.search.trim();
  if (term) params.set("search", term);
  if (values.category) params.set("category", values.category);
  if (values.kind) params.set("kind", values.kind);
  return params.size ? `/resources?${params.toString()}` : "/resources";
}

export function ResourceFilters({ search, category, kind }: { search?: string; category?: ResourceCategory; kind?: ResourceKind }) {
  const router = useRouter();
  const filtered = Boolean(search || category || kind);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    router.push(resourceFiltersHref({
      search: String(form.get("search") ?? ""),
      category: String(form.get("category") ?? ""),
      kind: String(form.get("kind") ?? ""),
    }));
  }

  return (
    <form role="search" aria-label="Search resources" onSubmit={submit} key={`${search ?? ""}:${category ?? ""}:${kind ?? ""}`}>
      <FilterToolbar
        fieldsClassName="lg:grid-cols-[minmax(0,1fr)_repeat(2,minmax(0,13rem))]"
        actions={<>
          {filtered ? <Link href="/resources" className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : null}
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
