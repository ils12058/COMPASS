"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Input } from "@/components/ui/input";

export function AnnouncementSearch({ search }: { search?: string }) {
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = String(new FormData(event.currentTarget).get("search") ?? "").trim();
    const params = new URLSearchParams();
    if (value) params.set("search", value);
    router.push(params.size ? `/announcements?${params.toString()}` : "/announcements");
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
