"use client";

import Link from "next/link";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { FeedbackAccessUnavailable, FeedbackPageHeading } from "@/features/feedback/feedback-shared";

export function FeedbackEntryPage() {
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);

  if (!access.hasWorkspace) return <FeedbackAccessUnavailable />;

  return (
    <section aria-labelledby="feedback-entry-heading">
      <FeedbackPageHeading headingId="feedback-entry-heading" title="Feedback" />
      {access.canSubmitCustomerFeedback || access.canSubmitCsm ? (
        <div className="mt-7">
          <h2 className="font-heading text-xl font-semibold text-ink">Submit a response</h2>
          <p className="mt-2 text-sm leading-6 text-muted">Each instrument is a separate final submission. There is no response history or editing after submission.</p>
          <ul className="mt-4 divide-y divide-border border-y border-border">
            {access.canSubmitCustomerFeedback ? <li className="py-5"><Link href="/portal/feedback/customer-feedback" className="font-semibold text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Customer Feedback Form</Link><p className="mt-1 text-sm text-muted">Share feedback on a service you received from the Guidance and Counseling Office.</p></li> : null}
            {access.canSubmitCsm ? <li className="py-5"><Link href="/portal/feedback/csm" className="font-semibold text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Client Satisfaction Measurement</Link><p className="mt-1 text-sm text-muted">Answer the Citizen&apos;s Charter and service quality questions.</p></li> : null}
          </ul>
        </div>
      ) : null}
      {access.canViewCustomerFeedback || access.canViewCsm ? (
        <div className="mt-9 border-t border-border pt-7">
          <h2 className="font-heading text-xl font-semibold text-ink">Review responses</h2>
          <ul className="mt-4 divide-y divide-border border-y border-border">
            {access.canViewCustomerFeedback ? <li className="py-5"><Link href="/portal/feedback/customer-feedback/responses" className="font-semibold text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Customer Feedback responses</Link><p className="mt-1 text-sm text-muted">Search, filter, and read stored Customer Feedback responses.</p></li> : null}
            {access.canViewCsm ? <li className="py-5"><Link href="/portal/feedback/csm/responses" className="font-semibold text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">CSM responses</Link><p className="mt-1 text-sm text-muted">Filter and read stored Client Satisfaction Measurement responses.</p></li> : null}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
