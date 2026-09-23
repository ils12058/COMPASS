import { ArrowLeft } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { PublicMaintenanceNotice } from "@/features/platform/platform-public-maintenance-notice";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh bg-surface lg:grid-cols-[minmax(0,1.05fr)_minmax(24rem,0.95fr)]">
      <main className="flex min-h-dvh flex-col px-5 py-6 sm:px-10 lg:px-14 xl:px-20">
        <Link
          href="/"
          aria-label="COMPASS public site"
          className="flex w-fit items-center gap-2 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <Image src="/brand/ucn-logo.png" width={32} height={30} alt="University of Camarines Norte" className="h-8 w-auto object-contain" priority />
          <span className="h-7 w-px bg-border" aria-hidden="true" />
          <Image src="/brand/compass-mark.svg" width={34} height={34} alt="" aria-hidden="true" />
          <span className="font-heading text-lg font-bold tracking-[0.08em] text-brand-strong">COMPASS</span>
        </Link>

        <div className="mx-auto mt-7 w-full max-w-md">
          <PublicMaintenanceNotice />
        </div>

        <div className="flex flex-1 items-center py-10">
          <div className="w-full max-w-md">{children}</div>
        </div>

        <Link
          href="/"
          className="inline-flex min-h-10 w-fit items-center gap-2 rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <ArrowLeft size={17} aria-hidden="true" />
          Back to public site
        </Link>
      </main>

      <aside className="auth-brand-panel relative hidden overflow-hidden text-on-brand lg:flex lg:flex-col lg:justify-end lg:p-12 xl:p-16">
        <div className="auth-campus absolute inset-0" aria-hidden="true" />
        <div className="absolute inset-0 bg-brand-strong/20" aria-hidden="true" />
        <div className="relative max-w-md">
          <p className="font-heading text-2xl font-bold">University of Camarines Norte</p>
          <p className="mt-2 leading-7 text-on-brand/80">Guidance and Counseling Office</p>
        </div>
      </aside>
    </div>
  );
}
