"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Input } from "@/components/ui/input";

// The canonical list URL for a submitted search: trimmed, without a page, and without the
// parameter when the search is blank.
export function announcementSearchHref(term: string): string {
  const value = term.trim();
  return value ? `/announcements?${new URLSearchParams({ search: value }).toString()}` : "/announcements";
}

export function AnnouncementSearch({ search }: { search?: string }) {
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push(announcementSearchHref(String(new FormData(event.currentTarget).get("search") ?? "")));
  }

  return (
    <form role="search" aria-label="Search announcements" onSubmit={submit}>
      <FilterToolbar
        fieldsClassName="sm:grid-cols-1 lg:grid-cols-[minmax(0,28rem)]"
        actions={<>
          {search ? <Link href="/announcements" className={buttonVariants({ variant: "quiet" })}>Clear search</Link> : null}
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
