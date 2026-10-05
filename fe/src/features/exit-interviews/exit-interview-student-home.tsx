"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DoorOpen } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { PageAction } from "@/components/ui/page-action";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import type { ExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import {
  ExitInterviewError, ExitInterviewHeading, ExitInterviewStatus,
  exitInterviewErrorMessage, isUncertainExitInterviewMutation,
  shouldHideExitInterviewCachedData,
} from "@/features/exit-interviews/exit-interview-shared";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";
import {
  exitInterviewsEnsureMyCurrent, getExitInterviewsGetMineQueryKey,
  getExitInterviewsGetMyStatusQueryKey, getExitInterviewsListMineQueryKey,
  useExitInterviewsGetMyStatus, useExitInterviewsListMine,
} from "@/lib/api/generated/exit-interviews/exit-interviews";

export function ExitInterviewStudentHome({ access }: { access: ExitInterviewAccess }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const current = useExitInterviewsGetMyStatus({ query: { enabled: access.canViewSelf, retry: false, refetchOnWindowFocus: true } });
  const history = useExitInterviewsListMine({ query: { enabled: access.canViewSelf, retry: false } });
  const start = useMutation({ mutationFn: () => exitInterviewsEnsureMyCurrent(), retry: false });
  const [startError, setStartError] = useState<unknown>();
  const [needsStatusCheck, setNeedsStatusCheck] = useState(false);
  const state = current.data?.data;
  const record = state?.current_record;
  const historicalItems = (history.data?.data.items ?? []).filter((item) => item.id !== record?.id);
  const hideHistory = history.isError && shouldHideExitInterviewCachedData(history.error);
  const canStart = !current.isError && access.canManageSelf && state?.can_start && !needsStatusCheck;

  async function handleStart() {
    setStartError(undefined);
    try {
      const result = await start.mutateAsync();
      queryClient.setQueryData(getExitInterviewsGetMineQueryKey(result.data.id), result);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getExitInterviewsGetMyStatusQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getExitInterviewsListMineQueryKey() }),
      ]);
      router.push(`/portal/exit-interviews/${result.data.id}`);
    } catch (error) {
      setStartError(error);
      setNeedsStatusCheck(isUncertainExitInterviewMutation(error));
      void current.refetch();
    }
  }

  async function checkStatus() {
    const result = await current.refetch();
    if (!result.isError) {
      setNeedsStatusCheck(false);
      setStartError(undefined);
    }
  }

  return (
    <section className="space-y-5" aria-labelledby="exit-interview-home-heading">
      <ExitInterviewHeading id="exit-interview-home-heading" title="Exit Interview"
        action={canStart ? <PageAction icon={DoorOpen} label="Start" labelDetail="Exit Interview" onClick={() => void handleStart()} disabled={start.isPending} /> : undefined} />
      <Panel aria-labelledby="exit-interview-current-heading">
        <PanelHeader title={state?.academic_year?.label ?? "Current Exit Interview"} titleId="exit-interview-current-heading" />
        {current.isPending ? (
          <LoadingRegion label="Loading Exit Interview access…" className="space-y-3 px-4 py-4 sm:px-5"><Skeleton className="h-8 w-48" /><Skeleton className="h-16 w-full" /></LoadingRegion>
        ) : current.isError ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void checkStatus()}>Retry</Button>}>
            {exitInterviewErrorMessage(current.error, "Your latest Exit Interview access could not be confirmed.")}
          </PanelMessage>
        ) : record ? (
          <div className="px-4 py-4 sm:px-5">
            <ExitInterviewStatus status={record.status} />
            <p className="mt-2 text-sm text-muted">{record.status === "SUBMITTED" ? "Head Guidance can review your submitted answers." : state?.can_edit_current ? "Your answers stay private until you submit." : "You can view this draft. Contact the Guidance and Counseling Office if you need to continue it."}</p>
            <Link href={`/portal/exit-interviews/${record.id}`} className={buttonVariants({ variant: state?.can_edit_current ? "primary" : "secondary", className: "mt-4" })}>
              {state?.can_edit_current ? "Continue Exit Interview" : record.status === "SUBMITTED" ? "View submitted Exit Interview" : "View draft Exit Interview"}
            </Link>
          </div>
        ) : state?.opportunity?.status === "OPEN" && access.canManageSelf ? (
          <PanelMessage action={!state.inventory_submitted ? <Link href="/portal/inventory" className={buttonVariants({ variant: "secondary" })}>Open Individual Inventory</Link> : undefined}>
            The Guidance and Counseling Office has opened an Exit Interview for you.
            {state.opportunity.source === "GRADUATION" ? " Submit it before requesting your graduation Good Moral certificate." : null}
            {!state.inventory_submitted ? " Submit your current Individual Inventory before starting." : null}
          </PanelMessage>
        ) : (
          <PanelMessage>{state?.opportunity?.status === "REVOKED" ? "The Guidance and Counseling Office has withdrawn your Exit Interview access." : state?.opportunity?.status === "COMPLETED" ? "Your Exit Interview workflow is completed." : "The Guidance and Counseling Office has not opened an Exit Interview for you."}</PanelMessage>
        )}
      </Panel>
      {startError ? <Notice role="alert" tone="danger" action={needsStatusCheck ? <Button variant="secondary" disabled={current.isFetching} onClick={() => void checkStatus()}>Check current status</Button> : undefined}>
        {needsStatusCheck ? "We could not confirm whether your Exit Interview started. Check its current status before trying again." : exitInterviewErrorMessage(startError, "The Exit Interview could not be started.")}
      </Notice> : null}
      <Panel aria-labelledby="exit-interview-history-heading">
        <PanelHeader title="Exit Interview history" titleId="exit-interview-history-heading" />
        {history.isPending ? <LoadingRegion label="Loading Exit Interview history…" className="px-4 py-4 sm:px-5"><Skeleton className="h-16 w-full" /></LoadingRegion> : history.isError && (!history.data || hideHistory) ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void history.refetch()}>Retry</Button>}>{exitInterviewErrorMessage(history.error, "Exit Interview history could not be loaded.")}</PanelMessage>
        ) : <>
          {history.isError ? <ExitInterviewError error={history.error} fallback="History could not be refreshed. Showing the last confirmed records." onRetry={() => void history.refetch()} /> : null}
          {historicalItems.length === 0 ? <PanelMessage>No other Exit Interview records.</PanelMessage> : <ul className="divide-y divide-border">
            {historicalItems.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-5">
              <div><Link href={`/portal/exit-interviews/${item.id}`} className="text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{item.academic_year.label}</Link><p className="mt-1 text-xs text-muted">Updated {formatExitInterviewDateTime(item.updated_at)}</p></div>
              <ExitInterviewStatus status={item.status} />
            </li>)}
          </ul>}
        </>}
      </Panel>
    </section>
  );
}
