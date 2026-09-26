import Link from "next/link";
import type { ReactNode } from "react";

export function WorkspaceUnavailable({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby="workspace-unavailable-heading"
      className="max-w-xl border-y border-border py-8"
    >
      <h1
        id="workspace-unavailable-heading"
        className="font-heading text-3xl font-bold text-ink"
      >
        {title}
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">{children}</p>
      <Link
        href="/portal"
        className="mt-5 inline-flex min-h-10 items-center text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Return to Overview
      </Link>
    </section>
  );
}
