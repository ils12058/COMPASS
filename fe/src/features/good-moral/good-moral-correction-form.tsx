"use client";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { GoodMoralDegreeInput } from "@/features/good-moral/good-moral-degree-input";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  GOOD_MORAL_SEMESTERS,
  GOOD_MORAL_YEAR_LEVELS,
  GoodMoralSection,
  goodMoralErrorCode,
  goodMoralErrorMessage,
  isCanonicalSemester,
  isCanonicalYearLevel,
  uncertainGoodMoralMutation,
} from "@/features/good-moral/good-moral-shared";
import { goodMoralUpdateRequest, getGoodMoralGetRequestQueryKey, getGoodMoralListRequestsQueryKey } from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralCorrectionPayload, GoodMoralOperationalDetailResponse } from "@/lib/api/generated/model";
import { institutionalDateInputValue } from "@/lib/institutional-time";

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

function draftFrom(item: GoodMoralOperationalDetailResponse): CorrectionDraft {
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

function correctionPayload(item: GoodMoralOperationalDetailResponse, draft: CorrectionDraft): GoodMoralCorrectionPayload {
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
  for (const field of Object.keys(changes) as (keyof GoodMoralCorrectionPayload)[]) {
    if (!item.actions.correction_fields.includes(field)) delete changes[field];
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
  confirmed = true,
  onSaved,
}: {
  item: GoodMoralOperationalDetailResponse;
  onRefresh: () => Promise<GoodMoralOperationalDetailResponse | undefined>;
  open: boolean;
  confirmed?: boolean;
  onSaved?: (message: string) => void;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const sending = useRef(false);
  const alive = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [working, setWorking] = useState(false);
  const [draft, setDraft] = useState(() => draftFrom(item));
  const [reviewedItem, setReviewedItem] = useState(item);
  const [reviewRequired, setReviewRequired] = useState(false);
  const operation = useRef<{ fingerprint: string; id: string } | null>(null);
  const ledgerActive = reviewedItem.receipt_identity?.ledger_mode === "ACTIVE";
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [blockedUntilRefresh, setBlockedUntilRefresh] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);
  const payload = useMemo(() => correctionPayload(ledgerActive ? reviewedItem : item, draft), [item, reviewedItem, ledgerActive, draft]);
  const hasChanges = Object.keys(payload).length > 0;
  const update = useMutation({
    mutationFn: (changes: GoodMoralCorrectionPayload) => goodMoralUpdateRequest(item.id, changes),
    retry: false,
  });

  const busy = update.isPending || working;

  function setField<K extends keyof CorrectionDraft>(field: K, value: CorrectionDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
    setError(null);
    setNotice(null);
  }

  async function refreshCanonical(preserveDraft = false): Promise<GoodMoralOperationalDetailResponse | undefined> {
    const refreshed = await onRefresh();
    if (!alive.current) return undefined;
    if (!refreshed) {
      setBlockedUntilRefresh(true);
      setError("The request could not be refreshed. Do not submit another correction until its current values can be checked.");
      return undefined;
    }
    if (!preserveDraft) setDraft(draftFrom(refreshed));
    else setReviewRequired(true);
    setReviewedItem(refreshed);
    setBlockedUntilRefresh(false);
    return refreshed;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    if (!confirmed || !hasChanges || reviewRequired || sending.current) return;
    let changes = payload;
    if (ledgerActive && ["official_receipt_number", "official_receipt_date", "official_receipt_amount"].some((name) => name in payload)) {
      const reviewed = {
        ...payload,
        expected_resource_version: reviewedItem.actions.request_version,
        expected_receipt_revision: reviewedItem.receipt_identity?.revision_id ?? null,
      };
      const fingerprint = JSON.stringify(reviewed);
      if (!operation.current || operation.current.fingerprint !== fingerprint) {
        if (!globalThis.crypto?.randomUUID) {
          setError("This browser cannot create a correction identity. Update the browser and try again.");
          return;
        }
        operation.current = { fingerprint, id: globalThis.crypto.randomUUID() };
      }
      changes = { ...reviewed, receipt_operation_id: operation.current.id };
    }
    sending.current = true;
    setWorking(true);
    try {
      await update.mutateAsync(changes);
      if (!alive.current) return;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(item.id) }),
        queryClient.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
        invalidateGuidanceWork(queryClient),
      ]);
      setNotice("Certificate details saved.");
      const refreshed = await refreshCanonical();
      if (refreshed) {
        const before = reviewedItem.receipt_inspection;
        const changedReceipt = reviewedItem.receipt_identity?.revision_id !== refreshed.receipt_identity?.revision_id;
        const retained = before?.status === "VERIFIED" && refreshed.receipt_inspection?.status === "VERIFIED" && before.verification_id === refreshed.receipt_inspection.verification_id;
        onSaved?.(changedReceipt && before?.status === "VERIFIED"
          ? "Certificate details saved. The updated receipt needs a new physical inspection before preparation."
          : retained ? `Certificate details saved. Receipt inspection retained.${reviewedItem.status === "READY_FOR_ISSUANCE" && refreshed.status === "REQUESTED" ? " Prepare this request again." : ""}`
          : "Certificate details saved.");
        onClose();
      }
    } catch (caught) {
      if (!alive.current) return;
      if (ledgerActive && (uncertainGoodMoralMutation(caught) || goodMoralErrorCode(caught) === "good_moral_receipt_changed")) {
        const refreshed = await refreshCanonical(true);
        if (refreshed) setReviewRequired(true);
        setError("The correction could not be confirmed against the details you reviewed. Your draft is kept; compare it with the latest saved receipt before continuing.");
        return;
      }
      if (uncertainGoodMoralMutation(caught)) {
        const refreshed = await refreshCanonical();
        if (refreshed?.status === "REQUESTED") {
          setError("The correction result could not be confirmed. The request has been refreshed; review its current values before saving again.");
        }
        return;
      }
      setError(goodMoralErrorMessage(caught, "Certificate details could not be corrected."));
    } finally {
      sending.current = false;
      if (alive.current) setWorking(false);
    }
  }

  function requestClose() {
    if (busy) return;
    if (hasChanges) {
      setDiscardOpen(true);
      return;
    }
    onClose();
  }

  function discardChanges() {
    setDraft(draftFrom(item));
    setReviewedItem(item);
    setReviewRequired(false);
    operation.current = null;
    setError(null);
    setNotice(null);
    setDiscardOpen(false);
    onClose();
  }

  if (!open) return null;
  const today = institutionalDateInputValue();

  return (
    <>
      <GoodMoralSection
        title="Correct certificate details"
        description="Changes apply only to this certificate. Saving a change returns a ready request to preparation."
      >
        <form onSubmit={submit} aria-busy={busy} className="max-w-4xl space-y-6">
          <fieldset disabled={busy || blockedUntilRefresh || !confirmed} className="space-y-5 disabled:opacity-80">
            <section aria-labelledby="good-moral-correction-certificate-heading">
              <h3 id="good-moral-correction-certificate-heading" className="text-sm font-semibold text-ink">Certificate details</h3>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {item.actions.correction_fields.includes("applicant_name") ? <div className="sm:col-span-2">
                  {correctionFieldLabel("applicant-name", "Applicant name", true)}
                  <Input id="good-moral-correction-applicant-name" className="mt-2" maxLength={200} value={draft.applicantName} onChange={(event) => setField("applicantName", event.target.value)} />
                </div> : null}
                {item.variant === "CURRENT_STUDENT" ? (
                  <>
                    <div>
                      {correctionFieldLabel("year-level", "Year Level")}
                      <Select
                        id="good-moral-correction-year-level"
                        className="mt-2"
                        value={draft.yearLevel}
                        onChange={(event) => setField("yearLevel", event.target.value)}
                      >
                        {!isCanonicalYearLevel(item.year_level) && item.year_level ? (
                          <option value={item.year_level}>
                            {item.year_level} (Current value as entered)
                          </option>
                        ) : null}
                        {!draft.yearLevel && !item.year_level ? (
                          <option value="">Select Year Level</option>
                        ) : null}
                        {GOOD_MORAL_YEAR_LEVELS.map((level) => (
                          <option key={level} value={level}>{level}</option>
                        ))}
                      </Select>
                      {!isCanonicalYearLevel(item.year_level) && item.year_level ? (
                        <p className="mt-1 text-xs text-muted">Historical value as entered: “{item.year_level}”. Select a standardized Year Level to update it.</p>
                      ) : null}
                      <p className="mt-1 text-xs text-muted">A changed Year Level must match the linked submitted Inventory. Saving a correction does not change the Inventory.</p>
                    </div>
                    {item.actions.correction_fields.includes("college") ? <div>{correctionFieldLabel("college", "College")}<Input id="good-moral-correction-college" className="mt-2" maxLength={160} value={draft.college} onChange={(event) => setField("college", event.target.value)} /></div> : null}
                    <div>{correctionFieldLabel("course", "Course")}<Input id="good-moral-correction-course" className="mt-2" maxLength={180} value={draft.course} onChange={(event) => setField("course", event.target.value)} /></div>
                    <div>{correctionFieldLabel("major", "Major")}<Input id="good-moral-correction-major" className="mt-2" maxLength={180} value={draft.major} onChange={(event) => setField("major", event.target.value)} /></div>
                    <div>
                      {correctionFieldLabel("semester", "Semester")}
                      <Select
                        id="good-moral-correction-semester"
                        className="mt-2"
                        value={draft.semester}
                        onChange={(event) => setField("semester", event.target.value)}
                      >
                        {!isCanonicalSemester(item.semester) && item.semester ? (
                          <option value={item.semester}>
                            {item.semester} (Current value as entered)
                          </option>
                        ) : null}
                        {!draft.semester && !item.semester ? (
                          <option value="">Select Semester</option>
                        ) : null}
                        {GOOD_MORAL_SEMESTERS.map((sem) => (
                          <option key={sem} value={sem}>{sem}</option>
                        ))}
                      </Select>
                      {!isCanonicalSemester(item.semester) && item.semester ? (
                        <p className="mt-1 text-xs text-muted">Historical value as entered: “{item.semester}”. Select a standardized Semester to update it.</p>
                      ) : null}
                    </div>
                  </>
                ) : (
                  <>
                    {item.actions.correction_fields.includes("degree") ? <GoodMoralDegreeInput id="good-moral-correction-degree" value={draft.degree} onChange={(value) => setField("degree", value)} required={false} /> : null}
                    <div>{correctionFieldLabel("major", "Major")}<Input id="good-moral-correction-major" className="mt-2" maxLength={180} value={draft.major} onChange={(event) => setField("major", event.target.value)} /></div>
                    {item.actions.correction_fields.includes("graduation_date") ? <div>{correctionFieldLabel("graduation-date", "Graduation date")}<Input id="good-moral-correction-graduation-date" className="mt-2" type="date" max={today} value={draft.graduationDate} onChange={(event) => setField("graduationDate", event.target.value)} /></div> : null}
                  </>
                )}
              </div>
            </section>

            <section aria-labelledby="good-moral-correction-receipt-heading" className="border-t border-border pt-5">
              {item.receipt_identity?.ledger_mode === "ACTIVE" ? <p className="mb-3 text-sm text-muted">Complete the receipt before inspection and preparation. Changing its number, date or amount requires inspection again.</p> : null}
              <h3 id="good-moral-correction-receipt-heading" className="text-sm font-semibold text-ink">Official Receipt {item.receipt_identity?.ledger_mode !== "ACTIVE" ? <span className="font-normal text-muted">(optional)</span> : null}</h3>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>{correctionFieldLabel("receipt-number", "Receipt number")}<Input id="good-moral-correction-receipt-number" className="mt-2" maxLength={96} value={draft.receiptNumber} onChange={(event) => setField("receiptNumber", event.target.value)} /></div>
                <div>{correctionFieldLabel("receipt-date", "Receipt date")}<Input id="good-moral-correction-receipt-date" className="mt-2" type="date" max={today} value={draft.receiptDate} onChange={(event) => setField("receiptDate", event.target.value)} /></div>
                <div>
                  {correctionFieldLabel("receipt-amount", "Receipt amount")}
                  <Input id="good-moral-correction-receipt-amount" className="mt-2" type="number" min="0" max="9999999999.99" step="0.01" inputMode="decimal" value={draft.receiptAmount} onChange={(event) => setField("receiptAmount", event.target.value)} />
                  <p className="mt-1 text-xs text-muted">Enter the actual amount printed on the receipt, up to two decimal places. Saving these details does not record a physical inspection.</p>
                </div>
              </div>
            </section>
          </fieldset>

          {!confirmed ? <p role="status" className="text-sm text-muted">Your draft is kept. Confirm the current request before saving another correction.</p> : null}
          {reviewRequired ? <div className="space-y-3" role="status">
            <p className="text-sm">Latest saved receipt: {reviewedItem.official_receipt_number || "No number"} · {reviewedItem.official_receipt_date || "No date"} · {reviewedItem.official_receipt_amount ?? "No amount"}. Your draft remains above.</p>
            <Button type="button" variant="secondary" onClick={() => { setReviewRequired(false); setError(null); }}>Continue with my reviewed draft</Button>
          </div> : null}
          {error ? <p role="alert" className="text-sm leading-6 text-danger">{error}</p> : null}
          {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
          {blockedUntilRefresh ? <Button type="button" variant="secondary" onClick={() => void refreshCanonical(ledgerActive)}>Refresh current request</Button> : null}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={busy || blockedUntilRefresh || reviewRequired || !hasChanges || !confirmed}>{busy ? "Saving changes…" : "Save changes"}</Button>
            <Button type="button" variant="secondary" onClick={requestClose} disabled={busy}>Close editor</Button>
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
