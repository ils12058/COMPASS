"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { PlatformTimestamp } from "@/features/platform/platform-presentation";
import {
  portalMaintenanceMode,
  useMaintenanceStatus,
  type MaintenancePhase,
} from "@/features/platform/maintenance-status";
import type { PlatformPublicStatusResponse } from "@/lib/api/generated/model";
import { INSTITUTION_TIME_ZONE } from "@/lib/institutional-time";

const checkedTime = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: INSTITUTION_TIME_ZONE });

// The maintenance message is written by an operator as plain text. It renders as text, keeping
// its line breaks, and is never interpreted as markup.
function MaintenanceMessage({ message, className }: { message: string | null; className?: string }) {
  if (!message) return null;
  return <p className={`whitespace-pre-wrap break-words ${className ?? ""}`}>{message}</p>;
}

// A compact, non-blocking notice. Pages show it only while maintenance is scheduled; while it is
// active they are replaced by the maintenance screen. Sign-in stays usable during maintenance, so
// it also shows the active state, without competing with the sign-in task.
export function MaintenanceNotice({ surface = "page" }: { surface?: "page" | "auth" }) {
  const { status, phase } = useMaintenanceStatus({ watch: surface === "auth" });
  if (!status) return null;
  if (phase === "scheduled") {
    return (
      <section role="status" aria-labelledby="scheduled-maintenance-heading" className="mb-5 rounded-sm border border-info/35 bg-surface-raised px-4 py-3 sm:px-5">
        <h2 id="scheduled-maintenance-heading" className="text-sm font-semibold text-ink">Scheduled maintenance</h2>
        <MaintenanceMessage message={status.message} className="mt-1 text-sm leading-6 text-ink" />
        {status.starts_at || status.ends_at ? (
          <p className="mt-1 text-sm text-muted">
            {status.starts_at ? <PlatformTimestamp value={status.starts_at} /> : null}
            {status.starts_at && status.ends_at ? <span aria-hidden="true"> – </span> : null}
            {status.starts_at && status.ends_at ? <span className="sr-only"> to </span> : null}
            {status.ends_at ? <PlatformTimestamp value={status.ends_at} /> : null}
          </p>
        ) : null}
      </section>
    );
  }
  if (phase === "active" && surface === "auth") {
    return (
      <section role="status" aria-labelledby="active-maintenance-heading" className="mb-4 rounded-sm border border-warning/40 bg-surface-raised px-4 py-3">
        <h2 id="active-maintenance-heading" className="text-sm font-semibold text-ink">COMPASS is under maintenance</h2>
        <p className="mt-0.5 text-sm text-muted">Most workspaces are temporarily unavailable.</p>
      </section>
    );
  }
  return null;
}

function MaintenanceBrand() {
  return (
    <div className="flex items-center gap-2 text-brand-strong">
      <Image src="/brand/ucn-logo.png" width={32} height={30} alt="" aria-hidden="true" className="h-8 w-auto object-contain" />
      <span className="h-7 w-px bg-border" aria-hidden="true" />
      <Image src="/brand/compass-mark.svg" width={36} height={36} alt="" aria-hidden="true" />
      <span className="font-heading text-lg font-bold tracking-[0.08em]">COMPASS</span>
    </div>
  );
}

// What a reader sees in place of COMPASS while maintenance is active: the operator's message, when
// the office expects to be back, and a way to ask again. It does not count down: COMPASS returns
// when the backend says so, not when a time passes.
export function MaintenanceScreen({
  status,
  heading,
  checking,
  checkedAt,
  onCheck,
  actions,
  controls,
}: {
  status: PlatformPublicStatusResponse;
  heading: string;
  checking: boolean;
  checkedAt: number | null;
  onCheck: () => void;
  // Further ways forward, such as signing in or opening Platform Operations.
  actions?: ReactNode;
  // Account and accessibility controls for the top of the page.
  controls?: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col bg-body">
      {controls ? <div className="flex justify-end gap-1 px-4 pt-3 sm:px-6">{controls}</div> : null}
      <main id="main-content" tabIndex={-1} className="flex flex-1 items-center px-4 py-10 focus:outline-none sm:px-6">
        <section aria-labelledby="maintenance-heading" className="mx-auto w-full max-w-lg rounded-sm border border-brand-line bg-surface-raised px-5 py-6 sm:px-8 sm:py-7">
          <div className="border-b border-border pb-5">
            <MaintenanceBrand />
            <p className="mt-2 text-sm font-medium text-muted">Guidance and Counseling Office</p>
          </div>
          <h1 id="maintenance-heading" className="mt-5 font-heading text-2xl font-bold leading-tight text-ink">{heading}</h1>
          <MaintenanceMessage message={status.message} className="mt-3 text-base leading-7 text-ink" />
          {status.ends_at ? (
            <dl className="mt-4">
              <dt className="text-sm font-semibold text-muted">Expected back</dt>
              <dd className="mt-0.5 text-base text-ink"><PlatformTimestamp value={status.ends_at} /></dd>
            </dl>
          ) : null}
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button disabled={checking} onClick={onCheck}>{checking ? "Checking…" : "Check again"}</Button>
            {actions}
          </div>
          {/* Said once per check the reader asked for; polling stays quiet. */}
          <p aria-live="polite" className="mt-3 min-h-5 text-sm text-muted">
            {checkedAt && !checking ? `Still under maintenance as of ${checkedTime.format(checkedAt)}.` : null}
          </p>
        </section>
      </main>
    </div>
  );
}

// The public site during maintenance: the ordinary page is replaced only once the backend confirms
// maintenance is active. While the status is unknown, or could not be read, the page renders.
export function PublicMaintenanceGate({ children }: { children: ReactNode }) {
  const { status, phase, checking, checkedAt, check } = useMaintenanceStatus({ watch: true });
  if (phase !== "active" || !status) return <>{children}</>;
  return (
    <MaintenanceScreen
      status={status}
      heading="COMPASS is temporarily unavailable"
      checking={checking}
      checkedAt={checkedAt}
      onCheck={() => void check()}
      actions={<Link href="/login" className={buttonVariants({ variant: "quiet" })}>Sign in</Link>}
    />
  );
}

// The authenticated portal during maintenance. Ordinary workspaces give way to the maintenance
// screen, so the dock and pages are not shown failing behind it. Platform Operations stays open to
// the accounts that can use it, in a frame that needs only the APIs maintenance leaves available.
export function PortalMaintenanceGate({
  pathname,
  canOperate,
  workspace,
  page,
  controls,
  loading,
}: {
  pathname: string;
  canOperate: boolean;
  // The ordinary shell with the page in it.
  workspace: ReactNode;
  // The page alone, for the recovery frame.
  page: ReactNode;
  controls: ReactNode;
  // Shown while the first status read is in flight, so a workspace is not shown and then replaced.
  loading?: ReactNode;
}) {
  const { status, phase, pending, checking, checkedAt, check } = useMaintenanceStatus({ watch: true });
  // An unanswered status read never holds the portal back for long; without a confirmed answer the
  // workspace renders.
  const [waited, setWaited] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setWaited(true), 3_000);
    return () => clearTimeout(timer);
  }, []);
  return (
    <PortalMaintenanceView
      status={status}
      phase={phase}
      pending={pending}
      pathname={pathname}
      canOperate={canOperate}
      workspace={workspace}
      page={page}
      controls={controls}
      checking={checking}
      checkedAt={checkedAt}
      onCheck={() => void check()}
      loading={waited ? null : loading}
    />
  );
}

export function PortalMaintenanceView({
  status,
  phase,
  pending,
  pathname,
  canOperate,
  workspace,
  page,
  controls,
  checking,
  checkedAt,
  onCheck,
  loading = null,
}: {
  status: PlatformPublicStatusResponse | undefined;
  phase: MaintenancePhase;
  pending: boolean;
  pathname: string;
  canOperate: boolean;
  workspace: ReactNode;
  page: ReactNode;
  controls: ReactNode;
  checking: boolean;
  checkedAt: number | null;
  onCheck: () => void;
  // Shown while the first status read is in flight.
  loading?: ReactNode;
}) {
  if (pending && loading) return <>{loading}</>;
  const mode = portalMaintenanceMode({ phase, pathname, canOperate });
  if (mode === "workspace" || !status) return <>{workspace}</>;
  if (mode === "recovery") return <PlatformRecoveryFrame controls={controls}>{page}</PlatformRecoveryFrame>;
  return (
    <MaintenanceScreen
      status={status}
      heading="COMPASS is under maintenance"
      checking={checking}
      checkedAt={checkedAt}
      onCheck={onCheck}
      controls={controls}
      actions={canOperate ? (
        <Link href="/portal/platform/maintenance" className={buttonVariants({ variant: "secondary" })}>
          Open Platform Operations
        </Link>
      ) : null}
    />
  );
}

// Platform Operations while maintenance is active, for the operators who can end it. It leaves out
// the dock and the notification bell, whose destinations and requests maintenance blocks.
export function PlatformRecoveryFrame({ controls, children }: { controls: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-body">
      <a
        href="#main-content"
        className="sr-only text-sm font-semibold text-brand focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:border focus:border-border-strong focus:bg-surface-raised focus:px-4 focus:py-3 focus:shadow-dialog focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Skip to main content
      </a>
      <header className="flex min-h-14 items-center justify-between gap-3 border-b border-border bg-surface-raised px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-2 text-brand-strong">
          <Image src="/brand/compass-mark.svg" width={28} height={28} alt="" aria-hidden="true" />
          <span className="font-heading text-base font-bold tracking-[0.08em] max-sm:sr-only">COMPASS</span>
        </div>
        <div className="flex shrink-0 items-center gap-1 sm:gap-2">{controls}</div>
      </header>
      <main id="main-content" tabIndex={-1} className="mx-auto max-w-[96rem] px-4 py-5 focus:outline-none sm:px-6 lg:px-8 lg:py-6">
        <p role="status" className="mb-5 rounded-sm border border-warning/40 bg-surface-raised px-4 py-3 text-sm text-ink sm:px-5">
          <span className="font-semibold">Maintenance Mode is active.</span> Other workspaces are unavailable until it ends.
        </p>
        {children}
      </main>
    </div>
  );
}
