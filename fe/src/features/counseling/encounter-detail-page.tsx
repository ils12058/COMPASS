"use client";

import Link from "next/link";
import { useState } from "react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { EncounterCorrectionForm } from "@/features/counseling/encounter-correction-form";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorMessage,
  CounselingPageHeading,
  CounselingQueryError,
  CounselingUnavailable,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { SharedSummarySection } from "@/features/counseling/shared-summary-section";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useCounselingGetEncounter } from "@/lib/api/generated/counseling/counseling";

function Metadata({ label, value }: { label: string; value: ReactNode }) {
  return <div className="border-b border-border/70 py-3"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm text-ink">{value}</dd></div>;
}

export function EncounterDetailPage({ encounterId }: { encounterId: string }) {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const query = useCounselingGetEncounter(encounterId, { query: { enabled: access.isCounselor && access.canViewAssigned, retry: false } });
  const encounter = query.data?.data;

  if (!access.isCounselor || !access.canViewAssigned) return <CounselingUnavailable title="Encounter unavailable" />;
  if (query.isPending) return <div aria-busy="true"><span className="sr-only">Loading assigned Counseling Encounter…</span><Skeleton className="h-10 w-2/3" /><Skeleton className="mt-4 h-28 w-full" /><Skeleton className="mt-5 h-48 w-full" /></div>;
  if (query.isError || !encounter) return <><CounselingPageHeading title="Counseling Encounter" action={<Link href="/portal/counseling" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">My Counseling Encounters</Link>} /><CounselingQueryError message={counselingErrorMessage(query.error, "This Counseling Encounter is not available within your current access.")} onRetry={() => void query.refetch()} /></>;

  return (
    <article>
      <CounselingPageHeading
        title="Counseling Encounter"
        description={`${encounter.student.display_name} · ${counselingEntryModeLabel(encounter.entry_mode)}`}
        action={<Link href="/portal/counseling" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">My Counseling Encounters</Link>}
      />

      <section aria-labelledby="encounter-details-heading">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
          <div><h2 id="encounter-details-heading" className="font-heading text-xl font-semibold text-ink">Recorded interaction details</h2><p className="mt-1 text-sm text-muted">This is a factual record of a completed Counseling interaction.</p></div>
          {access.canManageAssigned ? <Button variant="secondary" onClick={() => setCorrectionOpen((open) => !open)}>{correctionOpen ? "Close correction" : "Correct encounter details"}</Button> : null}
        </div>
        <dl className="grid gap-x-8 gap-y-2 border-b border-border py-4 sm:grid-cols-2 lg:grid-cols-3">
          <Metadata label="Student" value={encounter.student.display_name} />
          <Metadata label="Counselor" value={encounter.counselor.display_name} />
          <Metadata label="Service" value={<>{encounter.service.name}<span className="ml-2 font-mono text-xs text-muted">{encounter.service.code}</span></>} />
          <Metadata label="Appointment" value={encounter.appointment ? <Link href={`/portal/appointments/${encounter.appointment.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{encounter.appointment.reference_code}</Link> : "No linked Appointment"} />
          <Metadata label="Origin" value={counselingEntryModeLabel(encounter.entry_mode)} />
          <Metadata label="Delivery mode" value={counselingDeliveryModeLabel(encounter.delivery_mode)} />
          <Metadata label="Actual start" value={formatCounselingDateTime(encounter.started_at)} />
          <Metadata label="Actual end" value={formatCounselingDateTime(encounter.ended_at)} />
          <Metadata label="Recorded" value={formatCounselingDateTime(encounter.created_at)} />
          <Metadata label="Last updated" value={formatCounselingDateTime(encounter.updated_at)} />
        </dl>
        {correctionOpen && access.canManageAssigned ? <EncounterCorrectionForm encounter={encounter} onClose={() => setCorrectionOpen(false)} /> : null}
      </section>

      {access.canViewAssignedSummaries ? <div className="mt-8"><SharedSummarySection encounterId={encounter.id} access={access} /></div> : null}
    </article>
  );
}
