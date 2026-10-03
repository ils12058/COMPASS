"use client";

import Link from "next/link";
import { useState } from "react";
import type { ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { EncounterCorrectionForm } from "@/features/counseling/encounter-correction-form";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorMessage,
  CounselingPageHeading,
  CounselingQueryError,
  CounselingUnavailable,
  EncounterDetailSkeleton,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { SharedSummarySection } from "@/features/counseling/shared-summary-section";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useCounselingGetEncounter } from "@/lib/api/generated/counseling/counseling";

function Metadata({ label, value }: { label: string; value: ReactNode }) {
  return <div className="min-w-0"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm text-ink">{value}</dd></div>;
}

export function EncounterDetailPage({ encounterId }: { encounterId: string }) {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const query = useCounselingGetEncounter(encounterId, { query: { enabled: access.isCounselor && access.canViewAssigned, retry: false } });
  const encounter = query.data?.data;

  if (!access.isCounselor || !access.canViewAssigned) return <CounselingUnavailable title="Encounter unavailable" />;
  if (query.isPending) return <EncounterDetailSkeleton />;
  if (query.isError || !encounter) return <><CounselingPageHeading title="Counseling Encounter" action={<Link href="/portal/counseling" className={buttonVariants({ variant: "secondary" })}>My Counseling Encounters</Link>} /><CounselingQueryError message={counselingErrorMessage(query.error, "This counseling encounter is unavailable to this account.")} onRetry={() => void query.refetch()} /></>;

  return (
    <article>
      <CounselingPageHeading
        title="Counseling Encounter"
        description={`${encounter.student.display_name} · ${counselingEntryModeLabel(encounter.entry_mode)}`}
        action={<Link href="/portal/counseling" className={buttonVariants({ variant: "secondary" })}>My Counseling Encounters</Link>}
      />

      <Panel aria-labelledby="encounter-details-heading">
        <PanelHeader
          title="Recorded interaction details"
          titleId="encounter-details-heading"
          description="This is a factual record of a completed Counseling interaction."
          actions={access.canManageAssigned ? <Button variant="secondary" onClick={() => setCorrectionOpen((open) => !open)}>{correctionOpen ? "Close correction" : "Correct encounter details"}</Button> : undefined}
        />
        <dl className="grid gap-x-8 gap-y-4 px-4 py-4 sm:grid-cols-2 sm:px-5 lg:grid-cols-3">
          <Metadata label="Student" value={encounter.student.display_name} />
          <Metadata label="Counselor" value={encounter.counselor.display_name} />
          <Metadata label="Service" value={<>{encounter.service.name}</>} />
          <Metadata label="Appointment" value={encounter.appointment ? <Link href={`/portal/appointments/${encounter.appointment.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{encounter.appointment.reference_code}</Link> : "No linked Appointment"} />
          <Metadata label="Origin" value={counselingEntryModeLabel(encounter.entry_mode)} />
          <Metadata label="Delivery mode" value={counselingDeliveryModeLabel(encounter.delivery_mode)} />
          <Metadata label="Actual start" value={formatCounselingDateTime(encounter.started_at)} />
          <Metadata label="Actual end" value={formatCounselingDateTime(encounter.ended_at)} />
          <Metadata label="Recorded" value={formatCounselingDateTime(encounter.created_at)} />
          <Metadata label="Last updated" value={formatCounselingDateTime(encounter.updated_at)} />
        </dl>
        {correctionOpen && access.canManageAssigned ? <EncounterCorrectionForm encounter={encounter} onClose={() => setCorrectionOpen(false)} /> : null}
      </Panel>

      {access.canViewAssignedSummaries ? <div className="mt-5"><SharedSummarySection encounterId={encounter.id} access={access} /></div> : null}
    </article>
  );
}
