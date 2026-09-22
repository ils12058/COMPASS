"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CapabilityGate } from "@/features/content/components/capability-gate";
import { PublicationStatusBadge } from "@/features/content/components/publication-status-badge";
import {
  AUDIENCE_OPTIONS,
  RESOURCE_CATEGORY_OPTIONS,
  RESOURCE_KIND_OPTIONS,
  STATUS_OPTIONS,
  audienceLabel,
  formatContentDateTime,
  resourceCategoryLabel,
  resourceKindLabel,
} from "@/features/content/presentation";
import { useResourcesListManaged } from "@/lib/api/generated/resources/resources";
import type {
  ResourceAudienceValue,
  ResourceCategoryValue,
  ResourceKindValue,
  ResourceStatusValue,
} from "@/lib/api/generated/model";

export function ResourceManagementList() {
  return (
    <CapabilityGate capability="resources.manage">
      <ResourceManagementListInner />
    </CapabilityGate>
  );
}

function ResourceManagementListInner() {
  const [status, setStatus] = useState<ResourceStatusValue | "">("");
  const [audience, setAudience] = useState<ResourceAudienceValue | "">("");
  const [category, setCategory] = useState<ResourceCategoryValue | "">("");
  const [kind, setKind] = useState<ResourceKindValue | "">("");
  const [page, setPage] = useState(1);

  const query = useResourcesListManaged(
    {
      status: status || undefined,
      audience: audience || undefined,
      category: category || undefined,
      kind: kind || undefined,
      page,
      page_size: 20,
    },
    {
      query: {
        retry: false,
        placeholderData: (previous) => previous,
      },
    },
  );
  const data = query.data?.data;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <Link href="/portal/content" className="text-sm font-semibold no-underline">
            ← Content
          </Link>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Resources</h1>
          <p className="max-w-2xl text-muted-foreground">
            Manage articles, trusted links, forms, guides, and PDF resources.
          </p>
        </div>
        <Link
          href="/portal/content/resources/new"
          className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground no-underline hover:bg-[var(--compass-brand-maroon-strong)]"
        >
          <Plus aria-hidden="true" className="size-4" />
          New resource
        </Link>
      </header>

      <section
        aria-label="Resource filters"
        className="grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <FilterSelect
          label="Status"
          value={status}
          emptyLabel="All statuses"
          options={STATUS_OPTIONS}
          onChange={(value) => {
            setStatus(value as ResourceStatusValue | "");
            setPage(1);
          }}
        />
        <FilterSelect
          label="Audience"
          value={audience}
          emptyLabel="All audiences"
          options={AUDIENCE_OPTIONS}
          onChange={(value) => {
            setAudience(value as ResourceAudienceValue | "");
            setPage(1);
          }}
        />
        <FilterSelect
          label="Category"
          value={category}
          emptyLabel="All categories"
          options={RESOURCE_CATEGORY_OPTIONS}
          onChange={(value) => {
            setCategory(value as ResourceCategoryValue | "");
            setPage(1);
          }}
        />
        <FilterSelect
          label="Type"
          value={kind}
          emptyLabel="All resource types"
          options={RESOURCE_KIND_OPTIONS}
          onChange={(value) => {
            setKind(value as ResourceKindValue | "");
            setPage(1);
          }}
        />
      </section>

      {query.isPending ? (
        <p role="status" className="text-sm text-muted-foreground">Loading resources…</p>
      ) : query.isError || !data ? (
        <section className="rounded-xl border bg-card p-6">
          <p className="text-sm text-muted-foreground">Resources could not be loaded right now.</p>
          <button
            type="button"
            className="mt-4 text-sm font-semibold text-primary"
            onClick={() => void query.refetch()}
          >
            Try again
          </button>
        </section>
      ) : data.items.length === 0 ? (
        <section className="rounded-xl border bg-card p-8 text-center">
          <h2 className="font-heading text-xl font-bold">No resources found</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Adjust the filters or create a new resource.
          </p>
        </section>
      ) : (
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full min-w-[64rem] border-collapse text-left text-sm">
            <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-semibold">Title</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Audience</th>
                <th className="px-4 py-3 font-semibold">Type</th>
                <th className="px-4 py-3 font-semibold">Category</th>
                <th className="px-4 py-3 font-semibold">Updated</th>
                <th className="px-4 py-3 font-semibold">Updated by</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.items.map((item) => (
                <tr key={item.id} className="align-top">
                  <td className="px-4 py-4">
                    <Link
                      href={`/portal/content/resources/${item.id}`}
                      className="font-semibold no-underline hover:underline"
                    >
                      {item.title.trim() || "Untitled draft"}
                    </Link>
                  </td>
                  <td className="px-4 py-4">
                    <PublicationStatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-4">{audienceLabel(item.audience)}</td>
                  <td className="px-4 py-4">{resourceKindLabel(item.kind)}</td>
                  <td className="px-4 py-4">{resourceCategoryLabel(item.category)}</td>
                  <td className="px-4 py-4">{formatContentDateTime(item.updated_at)}</td>
                  <td className="px-4 py-4">{item.updated_by.display_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data ? (
        <nav className="flex items-center justify-between gap-4" aria-label="Resource pages">
          <button
            type="button"
            disabled={page <= 1 || query.isFetching}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            className="min-h-10 rounded-lg border bg-card px-4 py-2 text-sm font-semibold disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-muted-foreground">Page {data.page}</span>
          <button
            type="button"
            disabled={!data.has_next || query.isFetching}
            onClick={() => setPage((current) => current + 1)}
            className="min-h-10 rounded-lg border bg-card px-4 py-2 text-sm font-semibold disabled:opacity-50"
          >
            Next
          </button>
        </nav>
      ) : null}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  emptyLabel,
  options,
  onChange,
}: {
  label: string;
  value: string;
  emptyLabel: string;
  options: readonly { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-1.5 text-sm font-semibold">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-10 w-full rounded-lg border bg-card px-3 py-2 font-normal"
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
