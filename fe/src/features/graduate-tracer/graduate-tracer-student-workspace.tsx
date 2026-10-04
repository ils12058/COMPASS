"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { Notice } from "@/components/ui/notice";
import type { GraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { GraduateTracerForm, GraduateTracerFormSkeleton } from "@/features/graduate-tracer/graduate-tracer-form";
import { GraduateTracerResponse } from "@/features/graduate-tracer/graduate-tracer-response";
import { GraduateTracerError, GraduateTracerHeading, GraduateTracerStatus, graduateTracerErrorCode, graduateTracerErrorMessage, isUncertainGraduateTracerMutation } from "@/features/graduate-tracer/graduate-tracer-shared";
import { formatGraduateTracerDateTime } from "@/features/graduate-tracer/graduate-tracer-presentation";
import { getGraduateTracerGetMyResponseQueryKey, useGraduateTracerEnsureMyResponse, useGraduateTracerGetMyResponse } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import { CompassApiError } from "@/lib/api/errors";

export function GraduateTracerStudentWorkspace({ access }: { access: GraduateTracerAccess }) {
  const queryClient = useQueryClient();
  const response = useGraduateTracerGetMyResponse({ query: { enabled: access.canViewSelf, retry: false } });
  const start = useGraduateTracerEnsureMyResponse({ mutation: { retry: false } });
  const [startError, setStartError] = useState<string>();
  const [needsStatusCheck, setNeedsStatusCheck] = useState(false);
  const detail = response.data?.data;
  const isNotStarted = response.isError && graduateTracerErrorCode(response.error) === "graduate_tracer_not_found";
  const hideCached = response.error instanceof CompassApiError && (response.error.status === 401 || response.error.status === 403);

  async function beginSurvey() {
    setStartError(undefined);
    setNeedsStatusCheck(false);
    try {
      const result = await start.mutateAsync();
      queryClient.setQueryData(getGraduateTracerGetMyResponseQueryKey(), result);
    } catch (error) {
      setStartError(graduateTracerErrorMessage(error, "The Graduate Tracer response could not be started."));
      if (isUncertainGraduateTracerMutation(error)) {
        const check = await response.refetch();
        if (check.data?.data) {
          queryClient.setQueryData(getGraduateTracerGetMyResponseQueryKey(), check.data);
          setStartError(undefined);
          return;
        }
        setNeedsStatusCheck(true);
      }
    }
  }

  async function checkResponseStatus() {
    setNeedsStatusCheck(false);
    const check = await response.refetch();
    if (check.data?.data || (check.isError && graduateTracerErrorCode(check.error) === "graduate_tracer_not_found")) {
      setStartError(undefined);
      return;
    }
    setNeedsStatusCheck(true);
    setStartError(graduateTracerErrorMessage(check.error, "The response status could not be verified."));
  }

  if (!access.canViewSelf) {
    return (
      <section className="space-y-5">
        <GraduateTracerHeading title="Graduate Tracer Survey" />
        <Notice role="alert">Your Graduate Tracer response is unavailable to this account.</Notice>
      </section>
    );
  }

  if (response.isPending && !detail) {
    return <section className="space-y-5"><GraduateTracerHeading title="Graduate Tracer Survey" /><GraduateTracerFormSkeleton /></section>;
  }

  if (graduateTracerErrorCode(response.error) === "graduate_tracer_disposed") {
    return <section><GraduateTracerHeading title="Graduate Tracer Survey" /><Notice role="status">{graduateTracerErrorMessage(response.error, "Your personal response is no longer available.")}</Notice></section>;
  }

  if (hideCached) {
    return <section className="space-y-5"><GraduateTracerHeading title="Graduate Tracer Survey" /><GraduateTracerError error={response.error} fallback="Your Graduate Tracer response could not be loaded." onRetry={() => void response.refetch()} /></section>;
  }

  if (detail) {
    const submitted = detail.status === "SUBMITTED";
    const editable = !submitted && access.canManageSelf;
    return (
      <section className="space-y-5" aria-labelledby="graduate-tracer-student-heading">
        <GraduateTracerHeading
          id="graduate-tracer-student-heading"
          title="Graduate Tracer Survey"

          action={<GraduateTracerStatus submitted={submitted} />}
        />
        {response.isError ? <Notice role="alert" tone="warning"><span className="text-ink">The latest status could not be refreshed. Showing the last confirmed response.</span></Notice> : response.isFetching ? <p role="status" className="text-xs text-muted">Refreshing response status…</p> : null}
        {submitted ? (
          <div className="space-y-6">
            <p className="text-sm text-muted">Submitted {formatGraduateTracerDateTime(detail.submitted_at)}. This response is read-only.</p>
            <GraduateTracerResponse detail={detail} />
          </div>
        ) : editable ? (
          <GraduateTracerForm key={detail.id} detail={detail} />
        ) : (
          <div className="space-y-5">
            <Notice tone="warning"><span className="text-ink">This saved draft is read-only for this account.</span></Notice>
            <GraduateTracerResponse detail={detail} />
          </div>
        )}
      </section>
    );
  }

  if (response.isError && !isNotStarted) {
    return <section className="space-y-5"><GraduateTracerHeading title="Graduate Tracer Survey" /><GraduateTracerError error={response.error} fallback="Your Graduate Tracer response could not be loaded." onRetry={() => void response.refetch()} /></section>;
  }

  return (
    <section className="space-y-5" aria-labelledby="graduate-tracer-student-heading">
      <GraduateTracerHeading
        id="graduate-tracer-student-heading"
        title="Graduate Tracer Survey"
        description="This survey collects information about graduate education and employment experiences to support graduate employability research and curriculum improvement."
      />
      <div className="max-w-3xl rounded-sm border border-brand-line bg-surface-raised px-4 py-5 sm:px-5">
        <p className="text-sm leading-6 text-muted">Your response is treated confidentially. Only authorized Head Guidance reviewers can access it after you submit. Starting creates a private draft; it does not submit answers.</p>
        {access.canManageSelf ? (
          <>
            <Button className="mt-4" disabled={start.isPending || needsStatusCheck} onClick={() => void beginSurvey()}>
              {start.isPending ? "Starting…" : "Start Graduate Tracer Survey"}
            </Button>
            {startError ? <p role="alert" className="mt-3 text-sm leading-6 text-danger">{startError}</p> : null}
            {needsStatusCheck ? <Button className="mt-3" variant="secondary" onClick={() => void checkResponseStatus()} disabled={response.isFetching}>{response.isFetching ? "Checking…" : "Check response status"}</Button> : null}
          </>
        ) : (
          <p className="mt-4 text-sm leading-6 text-ink">You cannot start a Graduate Tracer response with this account.</p>
        )}
      </div>
    </section>
  );
}

export function GraduateTracerStudentWorkspaceSkeleton() {
  return <LoadingRegion label="Loading Graduate Tracer workspace…" className="space-y-5"><Skeleton className="h-10 w-72" /><Skeleton className="h-24 w-full max-w-3xl" /></LoadingRegion>;
}
