import { ArrowLeft } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { MaintenanceNotice } from "@/features/platform/maintenance-presentation";

export function AuthSurface({
  children,
  size = "compact",
}: {
  children: ReactNode;
  size?: "compact" | "wide";
}) {
  return (
    <div className={`mx-auto w-full ${size === "wide" ? "max-w-lg" : "max-w-md"}`}>
      <Link
        href="/"
        className="mb-4 flex min-h-10 w-fit items-center gap-2 rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body"
      >
        <ArrowLeft size={17} aria-hidden="true" />
        Back to public site
      </Link>

      <MaintenanceNotice surface="auth" />

      <div className="w-full rounded-sm border border-brand-line bg-surface-raised px-5 py-6 text-left sm:px-8 sm:py-7">
        <div className="mb-5 border-b border-border pb-5">
          <Link
            href="/"
            aria-label="COMPASS public site"
            className="flex w-fit items-center gap-2 rounded-sm text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body"
          >
            <Image src="/brand/ucn-logo.png" width={32} height={30} alt="" aria-hidden="true" className="h-8 w-auto object-contain" priority />
            <span className="h-7 w-px bg-border" aria-hidden="true" />
            <Image src="/brand/compass-mark.svg" width={36} height={36} alt="" aria-hidden="true" />
            <span className="font-heading text-lg font-bold tracking-[0.08em]">COMPASS</span>
          </Link>
          <p className="mt-2 text-sm font-medium text-muted">Guidance and Counseling Office</p>
        </div>

        {children}
      </div>
    </div>
  );
}
