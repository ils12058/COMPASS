"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import {
  FeedbackListSkeleton,
  FeedbackAccessUnavailable,
  FeedbackDate,
  FeedbackPageHeading,
  FeedbackQueryError,
  feedbackOpportunityId,
} from "@/features/feedback/feedback-shared";
import {
  useFeedbackGetMyOpportunity,
  useFeedbackListMyOpportunities,
} from "@/lib/api/generated/feedback/feedback";
import type { FeedbackOpportunityResponse } from "@/lib/api/generated/model";

function InstrumentAction({
  label,
  submitted,
  available,
  href,
}: {
  label: string;
  submitted: boolean;
  available: boolean;
  href: string;
}) {
  return (
    <div className="flex flex-col gap-2 border-t border-border py-3 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm font-medium text-ink">{label}</span>
      {submitted ? (
        <span className="text-sm text-muted">Submitted</span>
      ) : available ? (
        <Link
          href={href}
          className="text-sm font-semibold text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Give feedback
        </Link>
      ) : (
        <span className="text-sm text-muted">Not available</span>
      )}
    </div>
  );
}

function OpportunityRow({
  opportunity,
  highlighted = false,
}: {
  opportunity: FeedbackOpportunityResponse;
  highlighted?: boolean;
}) {
  const query = `?opportunity=${encodeURIComponent(opportunity.id)}`;
  return (
    <li
      className={`py-5 ${highlighted ? "border-l-2 border-brand pl-4" : ""}`}
    >
      <h3 className="font-heading text-lg font-semibold text-ink">
        {opportunity.service_label}
      </h3>
      <p className="mt-1 text-sm text-muted">
        Completed <FeedbackDate value={opportunity.service_completed_at} />
      </p>
      <div className="mt-4">
        <InstrumentAction
          label="Customer Feedback"
          submitted={opportunity.customer_feedback_submitted}
          available={opportunity.can_submit_customer_feedback}
          href={`/portal/feedback/customer-feedback${query}`}
        />
        <InstrumentAction
          label="Client Satisfaction Measurement"
          submitted={opportunity.csm_submitted}
          available={opportunity.can_submit_csm}
          href={`/portal/feedback/csm${query}`}
        />
      </div>
    </li>
  );
}

export function FeedbackEntryPage() {
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);
  const searchParams = useSearchParams();
  const selectedParam = searchParams.get("opportunity");
  const selectedId = feedbackOpportunityId(selectedParam);
  const invalidSelected = selectedParam !== null && selectedId === null;

  const opportunities = useFeedbackListMyOpportunities({
    query: {
      retry: false,
      enabled: access.hasStudentSubmissionAccess,
    },
  });
  const selected = useFeedbackGetMyOpportunity(selectedId ?? "", {
    query: {
      retry: false,
      enabled: access.hasStudentSubmissionAccess && selectedId !== null,
    },
  });

  if (!access.canOpenFeedback) return <FeedbackAccessUnavailable />;

  const pending = opportunities.data?.data ?? [];
  const selectedOpportunity = selected.data?.data;
  const selectedAlreadyListed =
    selectedOpportunity !== undefined &&
    pending.some((item) => item.id === selectedOpportunity.id);

  return (
    <section aria-labelledby="feedback-entry-heading">
      <FeedbackPageHeading
        headingId="feedback-entry-heading"
        title="Feedback"
        description={
          access.hasStudentSubmissionAccess
            ? "Give feedback on completed Guidance and Counseling Office services."
            : undefined
        }
      />

      {access.hasStudentSubmissionAccess ? (
        <section className="mt-7" aria-labelledby="feedback-services-heading">
          <h2
            id="feedback-services-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Completed services
          </h2>

          {invalidSelected ? (
            <p role="alert" className="mt-4 border-y border-border py-5 text-sm text-muted">
              This Feedback link is not available.
            </p>
          ) : selected.isError && selectedId ? (
            <div className="mt-4">
              <p role="alert" className="border-y border-border py-5 text-sm text-muted">
                This Feedback opportunity is not available.
              </p>
            </div>
          ) : null}

          {opportunities.isPending || (selectedId && selected.isPending) ? (
            <FeedbackListSkeleton label="Loading completed services…" />
          ) : null}

          {opportunities.isError ? (
            <div className="mt-4">
              <FeedbackQueryError
                error={opportunities.error}
                fallback="Completed services could not be loaded."
                onRetry={() => void opportunities.refetch()}
              />
            </div>
          ) : null}

          {!opportunities.isPending && !opportunities.isError ? (
            pending.length || (selectedOpportunity && !selectedAlreadyListed) ? (
              <ul className="mt-4 divide-y divide-border border-y border-border">
                {selectedOpportunity && !selectedAlreadyListed ? (
                  <OpportunityRow opportunity={selectedOpportunity} highlighted />
                ) : null}
                {pending.map((opportunity) => (
                  <OpportunityRow
                    key={opportunity.id}
                    opportunity={opportunity}
                    highlighted={opportunity.id === selectedId}
                  />
                ))}
              </ul>
            ) : (
              <p className="mt-4 border-y border-border py-6 text-sm text-muted">
                You do not currently have a completed service waiting for feedback.
              </p>
            )
          ) : null}
        </section>
      ) : null}

      {access.hasOperationalWorkspace ? (
        <section className="mt-9 border-t border-border pt-7">
          <h2 className="font-heading text-xl font-semibold text-ink">Review responses</h2>
          <ul className="mt-4 divide-y divide-border border-y border-border">
            {access.canViewCustomerFeedback ? (
              <li className="py-5">
                <Link
                  href="/portal/feedback/customer-feedback/responses"
                  className="font-semibold text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  Customer Feedback responses
                </Link>
                <p className="mt-1 text-sm text-muted">
                  Search, filter, and read stored Customer Feedback responses.
                </p>
              </li>
            ) : null}
            {access.canViewCsm ? (
              <li className="py-5">
                <Link
                  href="/portal/feedback/csm/responses"
                  className="font-semibold text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  CSM responses
                </Link>
                <p className="mt-1 text-sm text-muted">
                  Filter and read stored Client Satisfaction Measurement responses.
                </p>
              </li>
            ) : null}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
