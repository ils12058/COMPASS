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
import { Skeleton } from "@/components/ui/skeleton";
import { organizationErrorMessage } from "@/features/organization/components/organization-action";

export const selectClass =
  "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

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
  action,
}: {
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
        {title}
      </h1>
      {action}
    </div>
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
    <div className="min-w-0 flex-1">
      <Label htmlFor="organization-search">{label}</Label>
      <div className="relative mt-2">
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
    <div role="alert" className="border-y border-border py-6">
      <p className="text-sm text-danger">
        {organizationErrorMessage(error, fallback)}
      </p>
      <Button variant="secondary" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export function TableSkeleton() {
  return (
    <div className="mt-6 space-y-3" aria-busy="true">
      {Array.from({ length: 5 }, (_, index) => (
        <Skeleton key={index} className="h-14 w-full" />
      ))}
      <p className="sr-only">Loading Organization records…</p>
    </div>
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
