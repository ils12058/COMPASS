"use client";

import { Search } from "lucide-react";
import {
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { organizationErrorMessage } from "@/features/organization/components/organization-action";
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { PanelMessage } from "@/components/ui/panel";

export function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${
        active
          ? "border-success/30 bg-success/10 text-success"
          : "border-border bg-surface-muted text-muted"
      }`}
    >
      {active ? "Active" : "Inactive"}
    </span>
  );
}

export function PageHeading({
  title,
  headingId,
  description,
  action,
}: {
  title: string;
  headingId?: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <PageHeader
      title={title}
      headingId={headingId}
      description={description}
      actions={action}
    />
  );
}

export function SearchField({
  label,
  placeholder,
}: {
  label: string;
  placeholder: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current = (searchParams.get("search") ?? "").slice(0, 200);
  const [value, setValue] = useState(current);

  useEffect(() => {
    if (value === current) return;
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams.toString());
      const trimmed = value.trim();
      if (trimmed) next.set("search", trimmed);
      else next.delete("search");
      next.delete("page");
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [current, pathname, router, searchParams, value]);

  return (
    <div className="grid min-w-0 content-start gap-1.5">
      <Label htmlFor="organization-search">{label}</Label>
      <div className="relative">
        <Search
          size={18}
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-3 text-muted"
        />
        <Input
          id="organization-search"
          className="pl-10"
          maxLength={200}
          placeholder={placeholder}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
      </div>
    </div>
  );
}

export function QueryError({
  error,
  fallback,
  onRetry,
}: {
  error: unknown;
  fallback: string;
  onRetry: () => void;
}) {
  return (
    <Notice
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Retry</Button>}
    >
      {organizationErrorMessage(error, fallback)}
    </Notice>
  );
}

// The same failure, inside the results Panel that would have held the records.
export function PanelQueryError({
  error,
  fallback,
  onRetry,
}: {
  error: unknown;
  fallback: string;
  onRetry: () => void;
}) {
  return (
    <PanelMessage
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Retry</Button>}
    >
      {organizationErrorMessage(error, fallback)}
    </PanelMessage>
  );
}

export function TableSkeleton({
  label = "Loading Organization records…",
  framed = false,
}: {
  label?: string;
  framed?: boolean;
}) {
  return (
    <RowsSkeleton
      label={label}
      rows={5}
      framed={framed}
      className={framed ? "mt-5" : undefined}
    />
  );
}

export function replaceQueryParam(
  pathname: string,
  searchParams: URLSearchParams,
  key: string,
  value: string,
  resetPage = true,
): string {
  const next = new URLSearchParams(searchParams.toString());
  if (value) next.set(key, value);
  else next.delete(key);
  if (resetPage) next.delete("page");
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}
