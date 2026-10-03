import type { ReactNode } from "react";

export function AuthSurface({
  children,
  size = "compact",
}: {
  children: ReactNode;
  size?: "compact" | "wide";
}) {
  return (
    <div
      className={`mx-auto w-full rounded-sm border border-brand-line bg-surface-raised px-5 py-6 text-left sm:px-8 sm:py-7 ${
        size === "wide" ? "max-w-lg" : "max-w-md"
      }`}
    >
      {children}
    </div>
  );
}
