import type { ReactNode } from "react";

export function PublicPageHeader({ children }: { children: ReactNode }) {
  return (
    <div className="border-b border-brand-line bg-surface-raised">
      <div className="mx-auto max-w-6xl px-5 py-6 sm:px-8 sm:py-8">{children}</div>
    </div>
  );
}
