import type { ReactNode } from "react";

export function PublicPageHeader({ children }: { children: ReactNode }) {
  return (
    <div className="border-b border-border bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-12">{children}</div>
    </div>
  );
}
