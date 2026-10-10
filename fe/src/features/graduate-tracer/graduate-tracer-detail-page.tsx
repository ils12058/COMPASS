"use client";

import { LoadingRegion } from "@/components/ui/loading-region";
import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { GraduateTracerResponse } from "@/features/graduate-tracer/graduate-tracer-response";
import { GraduateTracerError, GraduateTracerHeading, graduateTracerErrorCode } from "@/features/graduate-tracer/graduate-tracer-shared";
import { formatGraduateTracerDateTime } from "@/features/graduate-tracer/graduate-tracer-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError } from "@/lib/api/errors";
import { useGraduateTracerGetResponse } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import { GraduateTracerStatusValue } from "@/lib/api/generated/model";

export function GraduateTracerDetailPage({ responseId }: { responseId: string }) {
  const { user } = usePortalSession();
  const access = getGraduateTracerAccess(user);
  const detail = useGraduateTracerGetResponse(responseId, { query: { enabled: access.canViewOperational, retry: false } });

  if (!access.canViewOperational) {
    return (
      <section className="space-y-5">
        <GraduateTracerHeading title="Graduate Tracer response" />
        <Notice role="alert">Submitted Graduate Tracer responses are unavailable to this account.</Notice>
      </section>
    );
  }

  if (detail.isPending) {
    return <LoadingRegion label="Loading Graduate Tracer response…" className="space-y-5"><Skeleton className="h-9 w-64 max-w-full" /><Skeleton className="h-20 w-full" /><Skeleton className="h-56 w-full" /></LoadingRegion>;
  }

  const response = detail.data?.data;
  const mustHideCached = detail.error instanceof CompassApiError && [401, 403, 404].includes(detail.error.status);
  if ((!response && detail.isError) || mustHideCached) {
    return (
      <section className="space-y-5">
        <GraduateTracerHeading title="Graduate Tracer response" back={<Link href="/portal/graduate-tracer" className={pageBackLinkClass}>Back to Graduate Tracer queue</Link>} />
        <GraduateTracerError error={detail.error} fallback={graduateTracerErrorCode(detail.error) === "graduate_tracer_not_submitted" ? "This response is not available because it has not been submitted." : "The submitted Graduate Tracer response could not be loaded."} onRetry={() => void detail.refetch()} />
      </section>
    );
  }

  if (!response) return null;
  if (response.status !== GraduateTracerStatusValue.SUBMITTED) {
    return (
      <section className="space-y-5">
        <GraduateTracerHeading title="Graduate Tracer response" back={<Link href="/portal/graduate-tracer" className={pageBackLinkClass}>Back to Graduate Tracer queue</Link>} />
        <Notice role="alert">This response has not been submitted, so it is not available for review.</Notice>
      </section>
    );
  }
  return (
    <section className="space-y-5">
      <GraduateTracerHeading
        back={<Link href="/portal/graduate-tracer" className={pageBackLinkClass}>Back to Graduate Tracer queue</Link>}
        title={response.name || response.student.display_name}
        description={
          response.student.institutional_id
            ? `Submitted Graduate Tracer response · ${response.student.institutional_id}`
            : "Submitted Graduate Tracer response"
        }
        meta={<span className="text-sm text-muted">Submitted {formatGraduateTracerDateTime(response.submitted_at)}</span>}
      />
      {detail.isFetching ? <p role="status" className="text-xs text-muted">Refreshing submitted response…</p> : null}
      {detail.isError ? <GraduateTracerError error={detail.error} fallback="The response could not be refreshed. Showing the last confirmed response." onRetry={() => void detail.refetch()} /> : null}
      <GraduateTracerResponse detail={response} />
    </section>
  );
}
