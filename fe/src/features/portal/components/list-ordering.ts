// No "use client": route pages read the parameter on the server, and the hook only runs in
// client components.
import { usePathname, useRouter, useSearchParams } from "next/navigation";

// URL state for a collection's ordering (ADR-090). The `ordering` parameter holds one value of the
// collection's closed, generated enum, or is absent. Absent means "the default for these
// filters", which the backend resolves and reports in the page it returns, so the frontend never
// re-derives a default that could disagree with the server.
export function readOrdering<T extends string>(
  value: string | null,
  values: Record<string, T>,
): T | undefined {
  return Object.values(values).find((candidate) => candidate === value);
}

// Choosing an ordering keeps search and filters and returns to page 1, because the old page number
// no longer points at the same rows.
export function withOrdering(current: URLSearchParams, next: string): URLSearchParams {
  const params = new URLSearchParams(current);
  params.set("ordering", next);
  params.delete("page");
  return params;
}

export function useListOrdering<T extends string>(values: Record<string, T>) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const requested = readOrdering(searchParams.get("ordering"), values);

  function setOrdering(next: T) {
    const params = withOrdering(new URLSearchParams(searchParams.toString()), next);
    router.push(pathname + "?" + params.toString(), { scroll: false });
  }

  return { requested, setOrdering };
}
