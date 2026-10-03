import { ArrowLeft } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import { PublicMaintenanceNotice } from "@/features/platform/platform-public-maintenance-notice";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-dvh overflow-x-clip bg-body">
      <main className="flex min-h-dvh items-center px-4 pb-24 pt-10 sm:px-6 sm:py-10">
        <div className="mx-auto w-full max-w-lg">
          <Link
            href="/"
            aria-label="COMPASS public site"
            className="mx-auto flex w-fit items-center gap-2 rounded-sm text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body"
          >
            <Image src="/brand/ucn-logo.png" width={32} height={30} alt="" aria-hidden="true" className="h-8 w-auto object-contain" priority />
            <span className="h-7 w-px bg-border" aria-hidden="true" />
            <Image src="/brand/compass-mark.svg" width={36} height={36} alt="" aria-hidden="true" />
            <span className="font-heading text-lg font-bold tracking-[0.08em]">COMPASS</span>
          </Link>
          <p className="mt-2 text-center text-sm font-medium text-muted">
            Guidance and Counseling Office
          </p>

          <div className="mt-6">
            <PublicMaintenanceNotice />
            {children}
          </div>

          <Link
            href="/"
            className="mx-auto mt-6 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body"
          >
            <ArrowLeft size={17} aria-hidden="true" />
            Back to public site
          </Link>
        </div>
      </main>

      <AccessibilityControl placement="floating" />
    </div>
  );
}
