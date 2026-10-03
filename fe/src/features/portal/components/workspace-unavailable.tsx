import Link from "next/link";
import type { ReactNode } from "react";

import { Notice } from "@/components/ui/notice";

export function WorkspaceUnavailable({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby="workspace-unavailable-heading" className="max-w-xl">
      <Notice
        className="px-5 py-6 sm:px-6"
        title={
          <h1
            id="workspace-unavailable-heading"
            className="font-heading text-2xl font-bold text-ink"
          >
            {title}
          </h1>
        }
        action={
          <Link
            href="/portal"
            className="inline-flex min-h-10 items-center text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Return to Overview
          </Link>
        }
      >
        {children}
      </Notice>
    </section>
  );
}
