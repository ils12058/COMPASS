"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { buttonVariants } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import {
  CounselingPageHeading,
  CounselingUnavailable,
  CounselingWorkspaceSkeleton,
  contextEncounterState,
  counselingErrorMessage,
} from "@/features/counseling/counseling-shared";
import {
  contextEncounterPreset,
  encounterReturnPath,
  type EncounterReturnTarget,
} from "@/features/counseling/encounter-origin";
import { RecordEncounterForm, encounterProvenanceNote, type EncounterTimes } from "@/features/counseling/record-encounter-form";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { getAppointmentsGetQueryKey } from "@/lib/api/generated/appointments/appointments";
import {
  getCounselingContextGetOverviewQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingContextGetOverview,
} from "@/lib/api/generated/counseling/counseling";
import { CounselingContextAnchorType } from "@/lib/api/generated/model";
import {
  getRoutineInterviewsGetAssignedQueryKey,
  getRoutineInterviewsListAssignedQueryKey,
  getRoutineInterviewsListEncounterCandidatesQueryKey,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

const EMPTY_TIMES: EncounterTimes = { startedAt: "", endedAt: "" };

/**
 * Record Counseling Encounter (EC-WS-2): the one place a Counselor documents an Appointment or a
 * direct Routine Interview interaction outside Finish counseling. Workspaces only link here. An
 * E-Counseling call stays connected in the portal call dock while this page is open.
 */
export function RecordEncounterPage({
  anchorType,
  anchorId,
  from,
}: {
  anchorType: CounselingContextAnchorType;
  anchorId: string;
  from: EncounterReturnTarget;
}) {
  const { user } = usePortalSession();
  const router = useRouter();
  const queryClient = useQueryClient();
  const access = getCounselingAccess(user);
  // Linking changes the Routine Interview, so recording for one also needs Routine management.
  const canRecord = access.isCounselor && access.canManageAssigned && (
    anchorType !== CounselingContextAnchorType.ROUTINE_INTERVIEW || getRoutineInterviewAccess(user).canManageAssigned
  );
  const overview = useCounselingContextGetOverview(anchorType, anchorId, {
    query: { enabled: canRecord, retry: false },
  });
  const [times, setTimes] = useState<EncounterTimes>(EMPTY_TIMES);
  const [saved, setSaved] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const back = encounterReturnPath(anchorType, anchorId, from);

  useUnsavedChangesGuard({
    dirty: !saved && Boolean(times.startedAt || times.endedAt),
    message: "Discard the encounter times you entered?",
  });

  if (!canRecord) return <CounselingUnavailable title="Recording unavailable">This account cannot record Counseling Encounters here.</CounselingUnavailable>;

  const heading = (
    <CounselingPageHeading
      title="Record Counseling Encounter"
      back={<GuardedPortalLink href={back.href} className={pageBackLinkClass}>{back.label}</GuardedPortalLink>}
    />
  );

  if (overview.isPending) return <>{heading}<CounselingWorkspaceSkeleton /></>;
  if (overview.isError || !overview.data?.data) {
    return (
      <>
        {heading}
        <Notice
          role="alert"
          className="max-w-3xl px-5 py-6 sm:px-6"
          title={<h2 className="font-heading text-xl font-semibold text-ink">This interaction can’t be recorded now</h2>}
          action={<Link href={back.href} className={buttonVariants({ variant: "secondary" })}>{back.label}</Link>}
        >
          {counselingErrorMessage(overview.error, "Its counseling details are not currently available.")}
        </Notice>
      </>
    );
  }

  const context = overview.data.data;
  const preset = contextEncounterPreset(anchorType, anchorId, context);
  const recorded = contextEncounterState(context) === "RECORDED" && context.matching_encounter;

  async function refreshSources() {
    const routineId = anchorType === CounselingContextAnchorType.ROUTINE_INTERVIEW ? anchorId : context.routine_interview?.id;
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(anchorType, anchorId) }),
      queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
      ...(routineId
        ? [
            queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetAssignedQueryKey(routineId) }),
            queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListEncounterCandidatesQueryKey(routineId) }),
            queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListAssignedQueryKey() }),
          ]
        : []),
      ...(anchorType === CounselingContextAnchorType.APPOINTMENT
        ? [queryClient.invalidateQueries({ queryKey: getAppointmentsGetQueryKey(anchorId) })]
        : []),
    ]);
  }

  if (recorded) {
    return (
      <>
        {heading}
        <Notice
          className="max-w-3xl px-5 py-6 sm:px-6"
          title={<h2 className="font-heading text-xl font-semibold text-ink">An encounter is already recorded</h2>}
          action={
            <>
              <Link href={`/portal/counseling/encounters/${context.matching_encounter!.id}`} className={buttonVariants({ variant: "secondary" })}>View encounter</Link>
              <Link href={back.href} className={buttonVariants({ variant: "quiet" })}>{back.label}</Link>
            </>
          }
        >
          {notice ?? "This interaction already has its Counseling Encounter."}
        </Notice>
      </>
    );
  }

  if (!preset) {
    return (
      <>
        {heading}
        <Notice
          role="alert"
          className="max-w-3xl px-5 py-6 sm:px-6"
          title={<h2 className="font-heading text-xl font-semibold text-ink">This interaction can’t be recorded here</h2>}
          action={<Link href={back.href} className={buttonVariants({ variant: "secondary" })}>{back.label}</Link>}
        >
          Review its visit type and delivery mode.
        </Notice>
      </>
    );
  }

  return (
    <>
      {heading}
      <p className="mb-5 max-w-3xl text-sm text-muted">{encounterProvenanceNote(preset.entryMode)} Recording audio or video during a session doesn’t record the encounter.</p>
      {notice ? <p role="status" className="mb-4 text-sm text-ink">{notice}</p> : null}
      <div className="max-w-3xl">
        <RecordEncounterForm
          preset={preset}
          initialTimes={times}
          onTimesChange={setTimes}
          onCancel={() => router.push(back.href)}
          onCreated={async (encounterId) => {
            setSaved(true);
            await refreshSources();
            router.push(`/portal/counseling/encounters/${encodeURIComponent(encounterId)}`);
          }}
          onAlreadyRecorded={async () => {
            setSaved(true);
            setNotice(anchorType === CounselingContextAnchorType.ROUTINE_INTERVIEW
              ? "This Routine Interview’s encounter was already recorded. The latest details are now shown."
              : "An encounter was already recorded for this Appointment. The latest details are now shown.");
            await refreshSources();
            await overview.refetch();
          }}
        />
      </div>
    </>
  );
}
