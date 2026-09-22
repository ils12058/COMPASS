"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PublicationStatusBadge } from "@/features/content/components/publication-status-badge";
import { CapabilityGate } from "@/features/content/components/capability-gate";
import {
  AUDIENCE_OPTIONS,
  STATUS_OPTIONS,
  audienceLabel,
  formatContentDateTime,
} from "@/features/content/presentation";
import {
  useAnnouncementsListManaged,
} from "@/lib/api/generated/announcements/announcements";
import type {
  AnnouncementAudienceValue,
  AnnouncementStatusValue,
} from "@/lib/api/generated/model";

export function AnnouncementManagementList() {
  return (
    <CapabilityGate capability="announcements.manage">
      <AnnouncementManagementListInner />
    </CapabilityGate>
  );
}

function AnnouncementManagementListInner() {
  const [status, setStatus] = useState<AnnouncementStatusValue | "">("");
  const [audience, setAudience] = useState<AnnouncementAudienceValue | "">("");
  const [page, setPage] = useState(1);

  const query = useAnnouncementsListManaged(
    {
      status: status || undefined,
      audience: audience || undefined,
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
          <h1 className="font-heading text-3xl font-bold tracking-tight">Announcements</h1>
          <p className="max-w-2xl text-muted-foreground">
            Create and manage office updates, reminders, and time-sensitive notices.
          </p>
        </div>
        <Link
          href="/portal/content/announcements/new"
          className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground no-underline hover:bg-[var(--compass-brand-maroon-strong)]"
        >
          <Plus aria-hidden="true" className="size-4" />
          New announcement
        </Link>
      </header>

      <section aria-label="Announcement filters" className="grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-2">
        <label className="space-y-1.5 text-sm font-semibold">
          <span>Status</span>
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as AnnouncementStatusValue | "");
              setPage(1);
            }}
            className="min-h-10 w-full rounded-lg border bg-card px-3 py-2 font-normal"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-sm font-semibold">
          <span>Audience</span>
          <select
            value={audience}
            onChange={(event) => {
              setAudience(event.target.value as AnnouncementAudienceValue | "");
              setPage(1);
            }}
            className="min-h-10 w-full rounded-lg border bg-card px-3 py-2 font-normal"
          >
            <option value="">All audiences</option>
            {AUDIENCE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </section>

      {query.isPending ? (
        <p role="status" className="text-sm text-muted-foreground">Loading announcements…</p>
      ) : query.isError || !data ? (
        <section className="rounded-xl border bg-card p-6">
          <p className="text-sm text-muted-foreground">
            Announcements could not be loaded right now.
          </p>
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
          <h2 className="font-heading text-xl font-bold">No announcements found</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Adjust the filters or create a new announcement.
          </p>
        </section>
      ) : (
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full min-w-[52rem] border-collapse text-left text-sm">
            <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-semibold">Title</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Audience</th>
                <th className="px-4 py-3 font-semibold">Pinned</th>
                <th className="px-4 py-3 font-semibold">Updated</th>
                <th className="px-4 py-3 font-semibold">Updated by</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.items.map((item) => (
                <tr key={item.id} className="align-top">
                  <td className="px-4 py-4">
                    <Link
                      href={`/portal/content/announcements/${item.id}`}
                      className="font-semibold no-underline hover:underline"
                    >
                      {item.title.trim() || "Untitled draft"}
                    </Link>
                  </td>
                  <td className="px-4 py-4">
                    <PublicationStatusBadge status={item.status} expiresAt={item.expires_at} />
                  </td>
                  <td className="px-4 py-4">{audienceLabel(item.audience)}</td>
                  <td className="px-4 py-4">{item.is_pinned ? "Yes" : "No"}</td>
                  <td className="px-4 py-4">{formatContentDateTime(item.updated_at)}</td>
                  <td className="px-4 py-4">{item.updated_by.display_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data ? (
        <nav className="flex items-center justify-between gap-4" aria-label="Announcement pages">
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
