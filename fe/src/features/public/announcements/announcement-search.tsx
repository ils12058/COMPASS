"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Input } from "@/components/ui/input";
import type { AnnouncementOrdering } from "@/lib/api/generated/model";

// The canonical list URL for a submitted search: trimmed, without a page, and without the
// parameter when the search is blank. A chosen order is kept; sorting is not a filter.
export function announcementSearchHref(term: string, ordering?: AnnouncementOrdering): string {
  const params = new URLSearchParams();
  const value = term.trim();
  if (value) params.set("search", value);
  if (ordering) params.set("ordering", ordering);
  const query = params.toString();
  return query ? `/announcements?${query}` : "/announcements";
}

export function AnnouncementSearch({
  search,
  ordering,
}: {
  search?: string;
  ordering?: AnnouncementOrdering;
}) {
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push(
      announcementSearchHref(String(new FormData(event.currentTarget).get("search") ?? ""), ordering),
    );
  }

  return (
    <form role="search" aria-label="Search announcements" onSubmit={submit}>
      <FilterToolbar
        fieldsClassName="sm:grid-cols-1 lg:grid-cols-[minmax(0,28rem)]"
        actions={<>
          {search ? <Link href={announcementSearchHref("", ordering)} className={buttonVariants({ variant: "quiet" })}>Clear search</Link> : null}
          <Button type="submit">Search</Button>
        </>}
      >
        <FilterField label="Search announcements" htmlFor="announcement-search">
          <Input id="announcement-search" name="search" type="search" placeholder="Search announcements" defaultValue={search} key={search} />
        </FilterField>
      </FilterToolbar>
    </form>
  );
}
