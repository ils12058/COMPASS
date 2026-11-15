"use client";

import type { ReactNode } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { scriptFontVariable } from "@/styles/script-font";

// One Home header for every role: the script greeting, the "Home" context, and the office date
// with the reader's role context. Role-specific commands stay in the caller's actions.
export function HomeHeader({
  greeting,
  date,
  roleContext,
  headingId,
  actions,
}: {
  greeting: string;
  date: string;
  roleContext: string | null;
  headingId: string;
  actions: ReactNode;
}) {
  return (
    <div data-orientation="home" className={scriptFontVariable}>
      <PageHeader
        title={
          <span className="inline-block max-w-full font-script text-3xl font-semibold leading-[1.1] [overflow-wrap:anywhere] sm:text-4xl">
            {greeting}
          </span>
        }
        headingId={headingId}
        context="Home"
        description={[date, roleContext].filter(Boolean).join(" · ")}
        actions={actions}
      />
    </div>
  );
}