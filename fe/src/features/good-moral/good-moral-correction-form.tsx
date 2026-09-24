"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GoodMoralSection, goodMoralErrorMessage, uncertainGoodMoralMutation } from "@/features/good-moral/good-moral-shared";
import { goodMoralUpdateRequest, getGoodMoralGetRequestQueryKey, getGoodMoralListRequestsQueryKey } from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralCorrectionPayload, GoodMoralDetailResponse } from "@/lib/api/generated/model";

type CorrectionDraft = {
  applicantName: string;
  yearLevel: string;
  college: string;
  course: string;
  major: string;
  semester: string;
  degree: string;
  graduationDate: string;
  receiptNumber: string;
  receiptDate: string;
  receiptAmount: string;
};

function draftFrom(item: GoodMoralDetailResponse): CorrectionDraft {
  return {
    applicantName: item.applicant_name,
    yearLevel: item.year_level,
    college: item.college,
    course: item.course,
    major: item.major,
    semester: item.semester,
    degree: item.degree,
    graduationDate: item.graduation_date ?? "",
    receiptNumber: item.official_receipt_number,
    receiptDate: item.official_receipt_date ?? "",
    receiptAmount: item.official_receipt_amount ?? "",
  };
}

function correctionPayload(item: GoodMoralDetailResponse, draft: CorrectionDraft): GoodMoralCorrectionPayload {
  const changes: GoodMoralCorrectionPayload = {};
  const changedText = (next: string, current: string) => next.trim() !== current.trim();

  if (changedText(draft.applicantName, item.applicant_name)) changes.applicant_name = draft.applicantName.trim();
  if (item.variant === "CURRENT_STUDENT") {
    if (changedText(draft.yearLevel, item.year_level)) changes.year_level = draft.yearLevel.trim();
    if (changedText(draft.college, item.college)) changes.college = draft.college.trim();
    if (changedText(draft.course, item.course)) changes.course = draft.course.trim();
    if (changedText(draft.major, item.major)) changes.major = draft.major.trim();
    if (changedText(draft.semester, item.semester)) changes.semester = draft.semester.trim();
  } else {
    if (changedText(draft.degree, item.degree)) changes.degree = draft.degree.trim();
    if (changedText(draft.major, item.major)) changes.major = draft.major.trim();
    if (draft.graduationDate !== (item.graduation_date ?? "")) {
      changes.graduation_date = draft.graduationDate || null;
    }
  }
  if (changedText(draft.receiptNumber, item.official_receipt_number)) {
    changes.official_receipt_number = draft.receiptNumber.trim();
  }
  if (draft.receiptDate !== (item.official_receipt_date ?? "")) {
    changes.official_receipt_date = draft.receiptDate || null;
  }
  if (draft.receiptAmount.trim() !== (item.official_receipt_amount ?? "")) {
    changes.official_receipt_amount = draft.receiptAmount.trim() || null;
  }
  return changes;
}

function correctionFieldLabel(fieldId: string, label: string, required = false) {
  return <Label htmlFor={`good-moral-correction-${fieldId}`}>{label}{required ? <span aria-hidden="true"> *</span> : null}</Label>;
}

export function GoodMoralCorrectionForm({
  item,
  onRefresh,
  open,
  onClose,
}: {
  item: GoodMoralDetailResponse;
  onRefresh: () => Promise<GoodMoralDetailResponse | undefined>;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(() => draftFrom(item));
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [blockedUntilRefresh, setBlockedUntilRefresh] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);
  const payload = useMemo(() => correctionPayload(item, draft), [item, draft]);
  const hasChanges = Object.keys(payload).length > 0;
  const update = useMutation({
    mutationFn: (changes: GoodMoralCorrectionPayload) => goodMoralUpdateRequest(item.id, changes),
    retry: false,
  });

  function setField<K extends keyof CorrectionDraft>(field: K, value: CorrectionDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
    setError(null);
    setNotice(null);
  }

  async function refreshCanonical(): Promise<GoodMoralDetailResponse | undefined> {
    const refreshed = await onRefresh();
    if (!refreshed) {
      setBlockedUntilRefresh(true);
      setError("The request could not be refreshed. Do not submit another correction until its current values can be checked.");
      return undefined;
    }
    setDraft(draftFrom(refreshed));
    setBlockedUntilRefresh(false);
    return refreshed;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    if (!hasChanges) return;
    try {
      await update.mutateAsync(payload);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(item.id) }),
        queryClient.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
      ]);
      setNotice("Certificate details saved.");
      const refreshed = await refreshCanonical();
      if (refreshed) onClose();
    } catch (caught) {
      if (uncertainGoodMoralMutation(caught)) {
        const refreshed = await refreshCanonical();
        if (refreshed?.status === "REQUESTED") {
          setError("The correction result could not be confirmed. The request has been refreshed; review its current values before saving again.");
        }
        return;
      }
      setError(goodMoralErrorMessage(caught, "Certificate details could not be corrected."));
    }
  }

  function requestClose() {
    if (update.isPending) return;
    if (hasChanges) {
      setDiscardOpen(true);
      return;
    }
    onClose();
  }

  function discardChanges() {
    setDraft(draftFrom(item));
    setError(null);
    setNotice(null);
    setDiscardOpen(false);
    onClose();
  }

  if (!open) return null;

  return (
    <>
      <GoodMoralSection title="Correct certificate details">
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Changes apply only to this Good Moral request and do not update the Student&apos;s Account, Individual Inventory, or Organization records.
        </p>
        <form onSubmit={submit} aria-busy={update.isPending} className="mt-5 max-w-4xl space-y-6">
          <fieldset disabled={update.isPending || blockedUntilRefresh} className="space-y-5 disabled:opacity-80">
            <section aria-labelledby="good-moral-correction-certificate-heading">
              <h3 id="good-moral-correction-certificate-heading" className="text-sm font-semibold text-ink">Certificate details</h3>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  {correctionFieldLabel("applicant-name", "Applicant name", true)}
                  <Input id="good-moral-correction-applicant-name" className="mt-2" maxLength={200} value={draft.applicantName} onChange={(event) => setField("applicantName", event.target.value)} />
                </div>
                {item.variant === "CURRENT_STUDENT" ? (
                  <>
                    <div>{correctionFieldLabel("year-level", "Year level")}<Input id="good-moral-correction-year-level" className="mt-2" maxLength={64} value={draft.yearLevel} onChange={(event) => setField("yearLevel", event.target.value)} /></div>
                    <div>{correctionFieldLabel("college", "College")}<Input id="good-moral-correction-college" className="mt-2" maxLength={160} value={draft.college} onChange={(event) => setField("college", event.target.value)} /></div>
                    <div>{correctionFieldLabel("course", "Course")}<Input id="good-moral-correction-course" className="mt-2" maxLength={180} value={draft.course} onChange={(event) => setField("course", event.target.value)} /></div>
                    <div>{correctionFieldLabel("major", "Major")}<Input id="good-moral-correction-major" className="mt-2" maxLength={180} value={draft.major} onChange={(event) => setField("major", event.target.value)} /></div>
                    <div>{correctionFieldLabel("semester", "Semester")}<Input id="good-moral-correction-semester" className="mt-2" maxLength={80} value={draft.semester} onChange={(event) => setField("semester", event.target.value)} /></div>
                  </>
                ) : (
                  <>
                    <div>{correctionFieldLabel("degree", "Degree")}<Input id="good-moral-correction-degree" className="mt-2" maxLength={255} value={draft.degree} onChange={(event) => setField("degree", event.target.value)} /></div>
                    <div>{correctionFieldLabel("major", "Major")}<Input id="good-moral-correction-major" className="mt-2" maxLength={180} value={draft.major} onChange={(event) => setField("major", event.target.value)} /></div>
                    <div>{correctionFieldLabel("graduation-date", "Graduation date")}<Input id="good-moral-correction-graduation-date" className="mt-2" type="date" value={draft.graduationDate} onChange={(event) => setField("graduationDate", event.target.value)} /></div>
                  </>
                )}
              </div>
            </section>

            <section aria-labelledby="good-moral-correction-receipt-heading" className="border-t border-border pt-5">
              <h3 id="good-moral-correction-receipt-heading" className="text-sm font-semibold text-ink">Official Receipt <span className="font-normal text-muted">(optional)</span></h3>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>{correctionFieldLabel("receipt-number", "Receipt number")}<Input id="good-moral-correction-receipt-number" className="mt-2" maxLength={96} value={draft.receiptNumber} onChange={(event) => setField("receiptNumber", event.target.value)} /></div>
                <div>{correctionFieldLabel("receipt-date", "Receipt date")}<Input id="good-moral-correction-receipt-date" className="mt-2" type="date" value={draft.receiptDate} onChange={(event) => setField("receiptDate", event.target.value)} /></div>
                <div>
                  {correctionFieldLabel("receipt-amount", "Receipt amount")}
                  <Input id="good-moral-correction-receipt-amount" className="mt-2" type="number" min="0" max="9999999999.99" step="0.01" inputMode="decimal" value={draft.receiptAmount} onChange={(event) => setField("receiptAmount", event.target.value)} />
                  <p className="mt-1 text-xs text-muted">Optional; nonnegative, up to two decimal places. No currency is specified here.</p>
                </div>
              </div>
            </section>
          </fieldset>

          {error ? <p role="alert" className="text-sm leading-6 text-danger">{error}</p> : null}
          {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
          {blockedUntilRefresh ? <Button type="button" variant="secondary" onClick={() => void refreshCanonical()}>Refresh current request</Button> : null}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={update.isPending || blockedUntilRefresh || !hasChanges}>{update.isPending ? "Saving changes…" : "Save changes"}</Button>
            <Button type="button" variant="secondary" onClick={requestClose} disabled={update.isPending}>Close editor</Button>
          </div>
        </form>
      </GoodMoralSection>

      <AlertDialog open={discardOpen} onOpenChange={setDiscardOpen}>
        <AlertDialogContent aria-describedby="good-moral-correction-discard-description">
          <AlertDialogTitle>Discard these certificate changes?</AlertDialogTitle>
          <AlertDialogDescription id="good-moral-correction-discard-description">Unsaved corrections and receipt edits will be lost. The request itself will not change.</AlertDialogDescription>
          <div className="mt-5 flex flex-wrap justify-end gap-3">
            <AlertDialogCancel asChild><Button variant="secondary">Keep editing</Button></AlertDialogCancel>
            <AlertDialogAction asChild><Button variant="danger" onClick={discardChanges}>Discard changes</Button></AlertDialogAction>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
