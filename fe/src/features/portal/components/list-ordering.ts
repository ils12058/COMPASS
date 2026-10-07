"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { readOrdering, withOrdering } from "@/features/portal/components/list-ordering-params";

// The reader's chosen ordering for a client-rendered collection, read from and written to the URL
// (ADR-090). Route pages that parse parameters on the server use list-ordering-params directly.
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
