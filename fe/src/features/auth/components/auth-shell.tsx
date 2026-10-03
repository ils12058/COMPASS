import { ArrowLeft } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import { PublicMaintenanceNotice } from "@/features/platform/platform-public-maintenance-notice";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="auth-entry relative min-h-dvh overflow-x-clip">
      <div className="auth-entry-campus pointer-events-none absolute inset-0" aria-hidden="true" />

      <main className="relative z-10 flex min-h-dvh items-center px-4 pb-10 pt-20 sm:px-6 sm:py-10">
        <div className="mx-auto w-full max-w-lg">
          <Link
            href="/"
            aria-label="COMPASS public site"
            className="mx-auto flex w-fit items-center gap-2 rounded-sm text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand focus-visible:ring-offset-2 focus-visible:ring-offset-brand-strong"
          >
            <Image src="/brand/ucn-logo.png" width={32} height={30} alt="" aria-hidden="true" className="h-8 w-auto object-contain brightness-0 invert" priority />
            <span className="h-7 w-px bg-on-brand/60" aria-hidden="true" />
            <Image src="/brand/compass-mark.svg" width={36} height={36} alt="" aria-hidden="true" />
            <span className="font-heading text-lg font-bold tracking-[0.08em]">COMPASS</span>
          </Link>
          <p className="mt-2 text-center text-sm font-medium text-on-brand">
            Guidance and Counseling Office
          </p>

          <div className="mt-6">
            <PublicMaintenanceNotice />
            {children}
          </div>

          <Link
            href="/"
            className="mx-auto mt-6 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-sm text-sm font-semibold text-on-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand focus-visible:ring-offset-2 focus-visible:ring-offset-brand-strong"
          >
            <ArrowLeft size={17} aria-hidden="true" />
            Back to public site
          </Link>
        </div>
      </main>

      <AccessibilityControl placement="auth" />
    </div>
  );
}
