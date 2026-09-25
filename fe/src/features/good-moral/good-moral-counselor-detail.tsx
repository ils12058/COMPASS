"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { GoodMoralCancelAction } from "@/features/good-moral/good-moral-cancellation-action";
import { GoodMoralCorrectionForm } from "@/features/good-moral/good-moral-correction-form";
import { GoodMoralIssueSection } from "@/features/good-moral/good-moral-issue-section";
import { GoodMoralPdfDownload } from "@/features/good-moral/good-moral-pdf";
import {
  GoodMoralError,
  GoodMoralField,
  GoodMoralSection,
  GoodMoralStatus,
  formatGoodMoralAmount,
  formatGoodMoralDate,
  formatGoodMoralDateTime,
  goodMoralErrorCode,
  goodMoralVariantLabel,
} from "@/features/good-moral/good-moral-shared";
import { useGoodMoralGetRequest } from "@/lib/api/generated/good-moral/good-moral";

export function GoodMoralCounselorDetail({
  requestId,
  canManage,
  canIssue,
}: {
  requestId: string;
  canManage: boolean;
  canIssue: boolean;
}) {
  const detail = useGoodMoralGetRequest(requestId, { query: { retry: false } });
  const [correctionOpen, setCorrectionOpen] = useState(false);

  if (detail.isPending) {
    return <div className="space-y-4" aria-busy="true"><span className="sr-only">Loading Good Moral request…</span><Skeleton className="h-10 w-1/2" /><Skeleton className="h-44 w-full" /><Skeleton className="h-32 w-full" /></div>;
  }
  if (detail.isError) {
    const notFound = goodMoralErrorCode(detail.error) === "good_moral_not_found";
    return (
      <section className="max-w-2xl space-y-5">
        <Link href="/portal/good-moral" className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Good Moral queue</Link>
        {notFound ? <div role="alert" className="border-y border-border py-6"><h1 className="font-heading text-2xl font-semibold text-ink">Good Moral request not found</h1></div> : <GoodMoralError error={detail.error} fallback="The Good Moral request could not be loaded." onRetry={() => void detail.refetch()} />}
      </section>
    );
  }

  const item = detail.data.data;
  const refresh = async () => {
    const result = await detail.refetch();
    return result.isError ? undefined : result.data?.data;
  };
  const hasReceipt = Boolean(item.official_receipt_number || item.official_receipt_date || item.official_receipt_amount !== null);

  return (
    <section className="space-y-6" aria-labelledby="good-moral-counselor-detail-heading">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Link href="/portal/good-moral" className="mb-3 inline-flex min-h-9 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Good Moral queue</Link>
          <h1 id="good-moral-counselor-detail-heading" className="font-heading text-3xl font-bold text-ink">Good Moral request</h1>
          <p className="mt-2 text-sm text-muted">{goodMoralVariantLabel(item.variant)} certificate</p>
        </div>
        <GoodMoralStatus status={item.status} />
      </div>

      <GoodMoralSection title="Request details" labelledBy="good-moral-counselor-request-details">
        <dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">
          <GoodMoralField label="Student" value={item.student.display_name} />
          <GoodMoralField label="Applicant name" value={item.applicant_name} />
          <GoodMoralField label="Requested" value={formatGoodMoralDateTime(item.created_at)} />
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
          {item.issued_at ? <GoodMoralField label="Issued" value={formatGoodMoralDateTime(item.issued_at)} /> : null}
          {item.cancelled_at ? <GoodMoralField label="Cancelled" value={formatGoodMoralDateTime(item.cancelled_at)} /> : null}
          {item.status === "ISSUED" ? <GoodMoralField label="Issued by" value={item.issued_by_name_snapshot} /> : null}
        </dl>
      </GoodMoralSection>

      <GoodMoralSection title="Official Receipt">
        <p className="mt-2 text-sm text-muted">Optional receipt facts only. COMPASS does not record payment status here.</p>
        <dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">
          <GoodMoralField label="Receipt number" value={item.official_receipt_number || "Not provided"} />
          <GoodMoralField label="Receipt date" value={formatGoodMoralDate(item.official_receipt_date)} />
          <GoodMoralField label="Receipt amount" value={formatGoodMoralAmount(item.official_receipt_amount)} />
        </dl>
        {!hasReceipt ? <p className="mt-4 text-xs text-muted">No Official Receipt details are recorded.</p> : null}
      </GoodMoralSection>

      {item.status === "REQUESTED" && canManage ? (
        correctionOpen ? (
          <>
            <GoodMoralCorrectionForm
              item={item}
              onRefresh={refresh}
              open={correctionOpen}
              onClose={() => setCorrectionOpen(false)}
            />
            <GoodMoralSection title="Request actions">
              <GoodMoralCancelAction requestId={item.id} studentFacing={false} onRefresh={refresh} />
            </GoodMoralSection>
          </>
        ) : (
          <GoodMoralSection title="Request actions">
            <div className="flex flex-wrap gap-3">
              <Button variant="secondary" onClick={() => setCorrectionOpen(true)}>Correct certificate details</Button>
              <GoodMoralCancelAction requestId={item.id} studentFacing={false} onRefresh={refresh} />
            </div>
          </GoodMoralSection>
        )
      ) : null}

      {item.status === "REQUESTED" && canIssue ? <GoodMoralIssueSection item={item} onRefresh={refresh} /> : null}

      {item.status === "ISSUED" ? (
        <>
          <GoodMoralSection title="Certificate issuance">
            <dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">
              <GoodMoralField label="Issued at" value={formatGoodMoralDateTime(item.issued_at)} />
              <GoodMoralField label="Issued by" value={item.issued_by_name_snapshot} />
              <GoodMoralField label="Official form code" value={item.form_revision?.official_code} />
              <GoodMoralField label="Official revision" value={item.form_revision?.official_revision ? `Revision ${item.form_revision.official_revision}` : null} />
              <GoodMoralField label="Internal schema version" value={item.form_revision ? String(item.form_revision.internal_schema_version) : null} />
              <GoodMoralField label="Document template version" value={item.document_template_version ? `Version ${item.document_template_version}` : null} />
            </dl>
          </GoodMoralSection>
          <GoodMoralPdfDownload requestId={item.id} studentFacing={false} />
        </>
      ) : null}

      {item.status === "CANCELLED" ? <p role="status" className="border-y border-border py-4 text-sm text-muted">This request was cancelled. Cancellation details are not shown here.</p> : null}
    </section>
  );
}
