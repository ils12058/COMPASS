"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { TotpStepUpPanel } from "@/features/auth/mfa/totp-step-up-panel";
import { GoodMoralField, GoodMoralSection, formatGoodMoralDate, goodMoralErrorCode, goodMoralErrorMessage, uncertainGoodMoralMutation } from "@/features/good-moral/good-moral-shared";
import { goodMoralIssueRequest, getGoodMoralGetRequestQueryKey, getGoodMoralListRequestsQueryKey } from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralDetailResponse } from "@/lib/api/generated/model";
import { authGetMfaStatus } from "@/lib/api/generated/auth/auth";

type IssueDialogMode = "verify" | "confirm" | null;

export function GoodMoralIssueSection({
  item,
  onRefresh,
}: {
  item: GoodMoralDetailResponse;
  onRefresh: () => Promise<GoodMoralDetailResponse | undefined>;
}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<IssueDialogMode>(null);
  const [checkingMfa, setCheckingMfa] = useState(false);
  const [verificationPending, setVerificationPending] = useState(false);
  const [mfaDisabled, setMfaDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [blockedUntilRefresh, setBlockedUntilRefresh] = useState(false);
  const issue = useMutation({ mutationFn: () => goodMoralIssueRequest(item.id), retry: false });

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(item.id) }),
      queryClient.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
    ]);
  }

  async function beginIssue() {
    setError(null);
    setNotice(null);
    setMfaDisabled(false);
    setCheckingMfa(true);
    try {
      const status = (await authGetMfaStatus()).data;
      if (!status.enabled) {
        setMfaDisabled(true);
        setError("Multi-factor authentication must be enabled before this certificate can be issued.");
      } else {
        setMode(status.recent ? "confirm" : "verify");
      }
    } catch (caught) {
      setError(goodMoralErrorMessage(caught, "MFA status could not be verified. Issuance is unavailable until the security check succeeds."));
    } finally {
      setCheckingMfa(false);
    }
  }

  async function handleRecentMfaRequired() {
    setMode(null);
    setError("Recent MFA is required. Verify again before confirming issuance.");
    try {
      const status = (await authGetMfaStatus()).data;
      if (!status.enabled) {
        setMfaDisabled(true);
        setError("Multi-factor authentication must be enabled before this certificate can be issued.");
      } else {
        setError(null);
        setMode("verify");
      }
    } catch (caught) {
      setError(goodMoralErrorMessage(caught, "MFA status could not be verified. Issuance is unavailable until the security check succeeds."));
    }
  }

  async function confirmIssue() {
    setError(null);
    setNotice(null);
    try {
      await issue.mutateAsync();
      await invalidate();
      await onRefresh();
      setMode(null);
      setNotice("Good Moral certificate issued.");
    } catch (caught) {
      const code = goodMoralErrorCode(caught);
      if (code === "recent_mfa_required") {
        await handleRecentMfaRequired();
        return;
      }
      if (code === "current_student_required") {
        await onRefresh();
        setMode(null);
        setError("This Current Student certificate can no longer be issued because the Student is no longer in CURRENT lifecycle.");
        return;
      }
      if (uncertainGoodMoralMutation(caught)) {
        setMode(null);
        const refreshed = await onRefresh();
        if (refreshed?.status === "ISSUED") {
          setBlockedUntilRefresh(false);
          await invalidate();
          setError(null);
          setNotice("Good Moral certificate issued.");
        } else if (refreshed?.status === "REQUESTED") {
          setBlockedUntilRefresh(false);
          setError("Issuance could not be confirmed. The request is still Requested; review the certificate details before deliberately trying again.");
        } else {
          setBlockedUntilRefresh(true);
          setError("Issuance could not be confirmed and the request could not be refreshed. Do not retry until its current state can be checked.");
        }
        return;
      }
      setError(goodMoralErrorMessage(caught, "The Good Moral certificate could not be issued."));
    }
  }

  async function refreshRequestState() {
    const refreshed = await onRefresh();
    if (refreshed?.status === "ISSUED") {
      setBlockedUntilRefresh(false);
      await invalidate();
      setError(null);
      setNotice("Good Moral certificate issued.");
    } else if (refreshed?.status === "REQUESTED") {
      setBlockedUntilRefresh(false);
      setError(null);
      setNotice("The request is still Requested. Review the current certificate details before deciding whether to issue it.");
    } else if (refreshed?.status === "CANCELLED") {
      setBlockedUntilRefresh(false);
      setError("This request was cancelled and cannot be issued.");
    } else {
      setBlockedUntilRefresh(true);
      setError("The request state still cannot be verified. Issuance remains unavailable until it can be refreshed.");
    }
  }

  function handleDialogOpenChange(nextOpen: boolean) {
    if (!nextOpen && (issue.isPending || verificationPending)) return;
    if (!nextOpen) {
      setMode(null);
      return;
    }
    if (mode === null) setMode("confirm");
  }

  return (
    <>
      <GoodMoralSection title="Issuance review">
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Review the certificate facts before issuing. Issuance freezes the approved Form Revision, document template version, issuance time, and issuing Counselor for this certificate.</p>
        <dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">
          <GoodMoralField label="Applicant name" value={item.applicant_name} />
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
          <GoodMoralField label="Official Receipt number" value={item.official_receipt_number} />
          <GoodMoralField label="Official Receipt date" value={formatGoodMoralDate(item.official_receipt_date)} />
          <GoodMoralField label="Official Receipt amount" value={item.official_receipt_amount} />
        </dl>
        <div className="mt-5 flex flex-col items-start gap-3">
          <Button onClick={() => void beginIssue()} disabled={checkingMfa || issue.isPending || blockedUntilRefresh}>
            {checkingMfa ? "Checking MFA…" : "Issue certificate"}
          </Button>
          {blockedUntilRefresh ? <Button variant="secondary" onClick={() => void refreshRequestState()}>Refresh request state</Button> : null}
          {mfaDisabled ? (
            <p className="max-w-2xl text-sm leading-6 text-muted">
              <Link href="/portal/account/security" className="font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Open account security</Link> to enable an authenticator before issuing a certificate.
            </p>
          ) : null}
          {error ? <p role="alert" className="max-w-2xl text-sm leading-6 text-danger">{error}</p> : null}
          {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
        </div>
      </GoodMoralSection>

      <Dialog open={mode !== null} onOpenChange={handleDialogOpenChange}>
        <DialogContent aria-describedby="good-moral-issue-dialog-description">
          {mode === "verify" ? (
            <>
              <DialogTitle>Verify your identity</DialogTitle>
              <DialogDescription id="good-moral-issue-dialog-description">Enter the current code from your authenticator app to continue issuing this certificate.</DialogDescription>
              <TotpStepUpPanel
                onVerified={() => setMode("confirm")}
                onCancel={() => setMode(null)}
                onPendingChange={setVerificationPending}
              />
            </>
          ) : mode === "confirm" ? (
            <>
              <DialogTitle>Issue Good Moral certificate?</DialogTitle>
              <DialogDescription id="good-moral-issue-dialog-description">Issuing freezes the approved Form Revision, document template version, issuance time, and issuing Counselor for this certificate.</DialogDescription>
              <dl className="mt-5 grid gap-x-6 gap-y-4 sm:grid-cols-2">
                <GoodMoralField label="Applicant name" value={item.applicant_name} />
                <GoodMoralField label="Variant" value={item.variant === "CURRENT_STUDENT" ? "Current Student" : "Graduate"} />
                {item.variant === "CURRENT_STUDENT" ? (
                  <>
                    <GoodMoralField label="Year level" value={item.year_level} />
                    <GoodMoralField label="College" value={item.college} />
                    <GoodMoralField label="Course" value={item.course} />
                    <GoodMoralField label="Semester" value={item.semester} />
                  </>
                ) : (
                  <>
                    <GoodMoralField label="Degree" value={item.degree} />
                    <GoodMoralField label="Graduation date" value={formatGoodMoralDate(item.graduation_date)} />
                  </>
                )}
              </dl>
              {error ? <p role="alert" className="mt-4 text-sm leading-6 text-danger">{error}</p> : null}
              <div className="mt-6 flex flex-wrap justify-end gap-3">
                <Button variant="secondary" onClick={() => setMode(null)} disabled={issue.isPending}>Cancel</Button>
                <Button onClick={() => void confirmIssue()} disabled={issue.isPending}>{issue.isPending ? "Issuing certificate…" : "Issue certificate"}</Button>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
