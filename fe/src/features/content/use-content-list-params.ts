"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

// The list URL after applying changes to the current query. Unchanged parameters stay; a filter
// change drops the page so the new results start on page 1.
export function contentListHref(
  pathname: string,
  current: URLSearchParams,
  changes: Record<string, string | null>,
  resetPage = true,
): string {
  const next = new URLSearchParams(current.toString());
  for (const [key, value] of Object.entries(changes)) {
    if (value) next.set(key, value);
    else next.delete(key);
  }
  if (resetPage) next.delete("page");
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

// Keeps list filters and the page number in the URL so they survive opening a
// record and returning. Filter changes reset to page 1.
export function useContentListParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = (() => {
    const parsed = Number(searchParams.get("page"));
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
  })();

  function hrefWith(changes: Record<string, string | null>, resetPage = true): string {
    return contentListHref(pathname, new URLSearchParams(searchParams.toString()), changes, resetPage);
  }

  function update(changes: Record<string, string | null>) {
    router.replace(hrefWith(changes), { scroll: false });
  }

  function setPage(nextPage: number) {
    router.push(hrefWith({ page: nextPage > 1 ? String(nextPage) : null }, false), { scroll: false });
  }

  return { searchParams, page, hrefWith, update, setPage };
}
