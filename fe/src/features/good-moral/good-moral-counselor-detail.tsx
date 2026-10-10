"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelSection, RecordSummary, type RecordFact } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { GoodMoralCancelAction } from "@/features/good-moral/good-moral-cancellation-action";
import { GoodMoralCorrectionForm } from "@/features/good-moral/good-moral-correction-form";
import { GoodMoralPreparationSection } from "@/features/good-moral/good-moral-preparation-section";
import { GoodMoralIssueSection } from "@/features/good-moral/good-moral-issue-section";
import { GoodMoralPdfDownload } from "@/features/good-moral/good-moral-pdf";
import {
  GoodMoralDetailSkeleton,
  GoodMoralError,
  GoodMoralField,
  GoodMoralHeading,
  GoodMoralSection,
  GoodMoralStatus,
  formatGoodMoralAmount,
  formatGoodMoralDate,
  formatGoodMoralDateTime,
  goodMoralErrorCode,
  goodMoralVariantLabel,
} from "@/features/good-moral/good-moral-shared";
import { useGoodMoralGetRequest } from "@/lib/api/generated/good-moral/good-moral";

const factGrid = "grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3";

function shown(value: string | null | undefined): string {
  return value?.trim() || "Not provided";
}

export function GoodMoralCounselorDetail({
  requestId,
  canManage,
  canIssue,
  canPrepare,
}: {
  requestId: string;
  canManage: boolean;
  canIssue: boolean;
  canPrepare: boolean;
}) {
  const detail = useGoodMoralGetRequest(requestId, { query: { retry: false } });
  const confirmed = safeQueryData(detail);
  const [correctionOpen, setCorrectionOpen] = useState(false);

  if (detail.isPending) {
    return <GoodMoralDetailSkeleton />;
  }
  if (!confirmed) {
    const notFound = goodMoralErrorCode(detail.error) === "good_moral_not_found";
    return (
      <section className="max-w-2xl space-y-5">
        <Link href="/portal/good-moral" className={pageBackLinkClass}>Back to Good Moral queue</Link>
        {notFound ? <div role="alert" className="rounded-sm border border-brand-line bg-surface-raised px-4 py-5 sm:px-5"><h1 className="font-heading text-2xl font-semibold text-ink">Good Moral request not found</h1></div> : <GoodMoralError error={detail.error} fallback="The Good Moral request could not be loaded." onRetry={() => void detail.refetch()} />}
      </section>
    );
  }

  const item = confirmed.data;
  const refresh = async () => {
    const result = await detail.refetch();
    return result.isError ? undefined : result.data?.data;
  };
  const hasReceipt = Boolean(item.official_receipt_number || item.official_receipt_date || item.official_receipt_amount !== null);
  // The facts a counselor checks first; the remaining request details follow in the same sheet.
  const keyFacts: RecordFact[] = [
    { label: "Institutional ID", value: shown(item.student_institutional_id) },
    { label: "Current Student account", value: shown(item.student.display_name) },
    { label: "Requested", value: formatGoodMoralDateTime(item.created_at) },
    ...(item.prepared_at ? [{ label: "Prepared by", value: item.prepared_by?.display_name ?? "Not recorded" }, { label: "Prepared at", value: formatGoodMoralDateTime(item.prepared_at) }] : []),
    ...(item.issued_at ? [{ label: "Issued", value: formatGoodMoralDateTime(item.issued_at) }] : []),
    ...(item.cancelled_at ? [{ label: "Cancelled", value: formatGoodMoralDateTime(item.cancelled_at) }] : []),
  ];

  return (
    <section className="space-y-5" aria-labelledby="good-moral-counselor-detail-heading">
      {detail.isError ? <RefreshFailureNotice onRetry={() => void detail.refetch()} retrying={detail.isFetching} /> : null}
      <GoodMoralHeading
        headingId="good-moral-counselor-detail-heading"
        title="Good Moral request"
        description={item.status === "ISSUED" ? `${goodMoralVariantLabel(item.variant)} certificate` : `${goodMoralVariantLabel(item.variant)} request`}
        back={<Link href="/portal/good-moral" className={pageBackLinkClass}>Back to Good Moral queue</Link>}
      />

      <Panel aria-labelledby="good-moral-counselor-applicant">
        <RecordSummary
          label="Applicant name on request"
          title={shown(item.applicant_name)}
          titleId="good-moral-counselor-applicant"
          status={<GoodMoralStatus status={item.status} />}
          facts={keyFacts}
        />
        <PanelSection title="Request details" titleId="good-moral-counselor-request-details">
          <dl className={factGrid}>
            {item.variant === "CURRENT_STUDENT" ? (
              <>
                <GoodMoralField label="Year level" value={item.year_level} />
                <GoodMoralField label="College" value={item.college} />
                <GoodMoralField label="Course" value={item.course} />
                <GoodMoralField label="Major" value={item.major} />
                <GoodMoralField label="Semester" value={item.semester} />
                <GoodMoralField label="Academic Year" value={item.academic_year?.label} />
              </>
            ) : (
              <>
                <GoodMoralField label="Degree" value={item.degree} />
                <GoodMoralField label="Major" value={item.major} />
                <GoodMoralField label="Graduation date" value={formatGoodMoralDate(item.graduation_date)} />
              </>
            )}
            {item.status === "ISSUED" ? <GoodMoralField label="Issuer name on certificate" value={item.issued_by_name_snapshot} /> : null}
          </dl>
        </PanelSection>
        <PanelSection
          title="Official Receipt"
          titleId="good-moral-counselor-receipt"
          description="Optional receipt details. Payment status isn’t tracked here."
        >
          <dl className={factGrid}>
            <GoodMoralField label="Receipt number" value={item.official_receipt_number || "Not provided"} />
            <GoodMoralField label="Receipt date" value={formatGoodMoralDate(item.official_receipt_date)} />
            <GoodMoralField label="Receipt amount" value={formatGoodMoralAmount(item.official_receipt_amount)} />
          </dl>
          {!hasReceipt ? <p className="mt-4 text-xs text-muted">No Official Receipt details are recorded.</p> : null}
        </PanelSection>
      </Panel>

      {((item.actions.can_correct && canPrepare) || (item.actions.can_cancel && canManage)) && !detail.isError ? (
        correctionOpen && item.actions.can_correct && canPrepare ? (
          <>
            <GoodMoralCorrectionForm
              item={item}
              onRefresh={refresh}
              open={correctionOpen}
              onClose={() => setCorrectionOpen(false)}
            />
            <GoodMoralSection title="Request actions">
              {canManage && item.actions.can_cancel ? <GoodMoralCancelAction requestId={item.id} studentFacing={false} onRefresh={refresh} /> : null}
            </GoodMoralSection>
          </>
        ) : (
          <GoodMoralSection title="Request actions">
            <div className="flex flex-wrap gap-3">
              {item.actions.can_correct && canPrepare ? <Button variant="secondary" onClick={() => setCorrectionOpen(true)}>Correct certificate details</Button> : null}
              {canManage && item.actions.can_cancel ? <GoodMoralCancelAction requestId={item.id} studentFacing={false} onRefresh={refresh} /> : null}
            </div>
          </GoodMoralSection>
        )
      ) : null}

      {canPrepare && (item.status === "REQUESTED" || item.status === "READY_FOR_ISSUANCE") && !detail.isError && !correctionOpen ? <GoodMoralPreparationSection item={item} onRefresh={refresh} /> : null}

      {item.actions.can_issue && canIssue && !detail.isError ? <GoodMoralIssueSection item={item} onRefresh={refresh} /> : null}

      {item.status === "ISSUED" ? (
        <GoodMoralSection title="Certificate issuance">
          <dl className={factGrid}>
            <GoodMoralField label="Issued at" value={formatGoodMoralDateTime(item.issued_at)} />
            <GoodMoralField label="Issuer name on certificate" value={item.issued_by_name_snapshot} />
            {item.issued_by ? <GoodMoralField label="Current issuer account" value={item.issued_by.display_name} /> : null}
            <GoodMoralField label="Official form code" value={item.form_revision?.official_code} />
            <GoodMoralField label="Official revision" value={item.form_revision?.official_revision ? `Revision ${item.form_revision.official_revision}` : null} />
          </dl>
          <div className="mt-5 border-t border-border pt-4">
            {item.actions.can_download && !detail.isError ? <GoodMoralPdfDownload requestId={item.id} studentFacing={false} /> : null}
          </div>
        </GoodMoralSection>
      ) : null}

      {item.status === "CANCELLED" ? (
        <GoodMoralSection title="Cancellation">
          <dl className={factGrid}>
            <GoodMoralField label="Cancelled by" value={item.cancellation?.cancelled_by?.display_name ?? "Not recorded"} />
            <GoodMoralField label="Reason" value={item.cancellation?.reason} />
          </dl>
        </GoodMoralSection>
      ) : null}
    </section>
  );
}
