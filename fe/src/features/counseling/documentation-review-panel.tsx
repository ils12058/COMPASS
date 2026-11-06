"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { PersonAvatar } from "@/features/account/components/person-avatar";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { Button, buttonVariants } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import type { CounselingAccess } from "@/features/counseling/counseling-access";
import {
  counselingErrorMessage,
  CounselingListSkeleton,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import {
  appointmentDetailHref,
  documentationReviewReasonCopy,
  encounterDetailHref,
  reviewHref,
  reviewPageFromParam,
} from "@/features/counseling/documentation-review";
import { useCounselingListDocumentationReview } from "@/lib/api/generated/counseling/counseling";

// Five rows keeps this worklist beside the encounters it points at, not above them.
const REVIEW_PAGE_SIZE = 5;

export function DocumentationReviewPanel({ access }: { access: CounselingAccess }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user } = usePortalSession();
  const canReviewAppointments = getAppointmentAccess(user).canManage;
  const requestedPage = reviewPageFromParam(searchParams.get("review_page"));
  const review = useCounselingListDocumentationReview(
    { page: requestedPage, page_size: REVIEW_PAGE_SIZE },
    // Deliberately never cached: reconciling an Appointment elsewhere must change what is shown
    // here the moment the Counselor comes back.
    { query: { enabled: access.canViewAssigned, retry: false, staleTime: 0 } },
  );
  const result = review.data?.data;

  if (!access.canViewAssigned) return null;

  if (review.isPending) {
    return (
      <Panel aria-labelledby="needs-documentation-heading" className="mb-5">
        <PanelHeader title="Needs documentation" titleId="needs-documentation-heading" />
        <CounselingListSkeleton
          label="Loading appointments that need documentation…"
          framed={false}
        />
      </Panel>
    );
  }

  if (review.isError && !result) {
    return (
      <Panel aria-labelledby="needs-documentation-heading" className="mb-5">
        <PanelHeader title="Needs documentation" titleId="needs-documentation-heading" />
        <PanelMessage
          role="alert"
          tone="danger"
          action={<Button variant="secondary" onClick={() => void review.refetch()}>Retry</Button>}
        >
          {counselingErrorMessage(review.error, "Needs documentation could not be loaded.")}
        </PanelMessage>
      </Panel>
    );
  }

  if (!result) return null;

  if (result.items.length === 0) {
    // An empty first page is not news; a stranded review_page still has to lead back.
    if (requestedPage === 1) return null;
    return (
      <Panel aria-labelledby="needs-documentation-heading" className="mb-5">
        <PanelHeader title="Needs documentation" titleId="needs-documentation-heading" />
        <PanelMessage>
          No appointments on this page need documentation.{" "}
          <Link
            className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            href={reviewHref(pathname, new URLSearchParams(searchParams.toString()), 1)}
          >
            Back to the first page
          </Link>
        </PanelMessage>
      </Panel>
    );
  }

  return (
    <Panel aria-labelledby="needs-documentation-heading" className="mb-5">
      <PanelHeader
        title="Needs documentation"
        titleId="needs-documentation-heading"
        description="Appointments of yours that may need a record or reconciliation. This list is derived from current records and doesn’t confirm that Counseling took place."
        context={describeResultPage({
          count: result.items.length,
          page: result.page,
          hasNext: result.has_next,
          noun: { one: "appointment", other: "appointments" },
        })}
      />
      {/* A failed refresh of this projection keeps the last rows and says so; it never retries. */}
      {review.isError ? (
        <RefreshFailureNotice
          message="The latest Needs documentation results could not be loaded. Showing the last confirmed results."
          onRetry={() => void review.refetch()}
          retrying={review.isFetching}
        />
      ) : null}
      <ul className="divide-y divide-brand-line">
        {result.items.map((item) => {
          const copy = documentationReviewReasonCopy[item.reason];
          return (
            <li key={item.appointment_id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3 sm:px-5">
              <div className="min-w-0">
                <span className="flex items-center gap-2">
                  <PersonAvatar
                    displayName={item.student.display_name}
                    photoUrl={item.student.profile_photo_url}
                    photoUpdatedAt={item.student.profile_photo_updated_at}
                    size="compact"
                  />
                  <span className="font-semibold text-ink">{item.student.display_name}</span>
                </span>
                {item.student.institutional_id ? (
                  <span className="mt-1 block text-xs text-muted">{item.student.institutional_id}</span>
                ) : null}
                <p className="mt-1 text-sm text-muted">
                  {item.reference_code} · {formatCounselingDateTime(item.starts_at)} – {formatCounselingDateTime(item.ends_at)}
                </p>
                <p className="mt-2 text-sm font-semibold text-ink">{copy.label}</p>
                <p className="mt-1 text-sm text-muted">{copy.message}</p>
              </div>
              <span className="flex flex-wrap gap-2">
                {canReviewAppointments ? (
                  <Link
                    className={buttonVariants({ variant: "secondary" })}
                    href={appointmentDetailHref(item.appointment_id)}
                  >
                    Review appointment
                  </Link>
                ) : null}
                {item.encounter_id ? (
                  <Link
                    className={buttonVariants({ variant: "secondary" })}
                    href={encounterDetailHref(item.encounter_id)}
                  >
                    View encounter
                  </Link>
                ) : null}
              </span>
            </li>
          );
        })}
      </ul>
      <CanonicalPagination
        className="border-brand-line px-4 py-3 sm:px-5"
        label="Needs documentation pages"
        page={result.page}
        hasNext={result.has_next}
        onPageChange={(page) =>
          router.push(reviewHref(pathname, new URLSearchParams(searchParams.toString()), page), { scroll: false })
        }
      />
    </Panel>
  );
}
