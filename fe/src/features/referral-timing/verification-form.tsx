"use client";

import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { referralsRecordTimingVerification } from "@/lib/api/generated/referrals/referrals";
import { ReferralTimingSource } from "@/lib/api/generated/model";
import type { ReferralTimingResponse, ReferralTimingVerificationRequest } from "@/lib/api/generated/model";
import { emptyTimingDraft, focusTimingError, timingBackendErrors, timingDraftDirty, timingWindowsRequest, validateTimingDraft, type TimingFieldErrors } from "./timing-draft";
import { TimingEditor } from "./timing-editor";
import { confirmationSourceLabels } from "./timing-readout";

export function TimingVerificationForm({ facts, unavailable, onRefresh }: {
  facts: ReferralTimingResponse; unavailable: boolean; onRefresh: () => Promise<unknown>;
}) {
  const [draft, setDraft] = useState(emptyTimingDraft);
  const [source, setSource] = useState<ReferralTimingSource | "">("");
  const [errors, setErrors] = useState<TimingFieldErrors>({});
  const [error, setError] = useState("");
  const [baseline, setBaseline] = useState(() => ({ latest: facts.latest_verification_id, updated: facts.referral_updated_at }));
  const [reviewRequired, setReviewRequired] = useState(false);
  const intent = useRef<ReferralTimingVerificationRequest | null>(null);
  const busy = useRef(false);
  const status = useActionStatus();
  const changed = reviewRequired || baseline.latest !== facts.latest_verification_id || baseline.updated !== facts.referral_updated_at;
  useUnsavedChangesGuard({ dirty: timingDraftDirty(draft) || source !== "", message: "Discard your unsaved availability verification? Its scheduling information is kept only on this page." });
  const mutation = useMutation({ retry: false, gcTime: 0, mutationFn: async () => {
    if (!intent.current) throw new Error("Missing intended verification");
    await referralsRecordTimingVerification(facts.referral_id, intent.current);
  } });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current || unavailable || changed || !facts.can_verify) return;
    status.dismiss(); setError("");
    const invalid = validateTimingDraft(draft, { verification: true });
    if (!source) invalid.confirmation_source = "Choose how the time was confirmed.";
    setErrors(invalid);
    if (Object.keys(invalid).length) { focusTimingError("verification-timing", draft, invalid); return; }
    if (!source || (draft.answer !== "KNOWN" && draft.answer !== "NO_SUITABLE_TIME")) return;
    intent.current = { answer_kind: draft.answer, confirmation_source: source, windows: timingWindowsRequest(draft), note: draft.note, expected_latest_verification_id: baseline.latest, expected_referral_updated_at: baseline.updated };
    busy.current = true;
    try {
      await mutation.mutateAsync();
      intent.current = null;
      setDraft(emptyTimingDraft()); setSource(""); setErrors({});
      const updated = await onRefresh();
      if (updated && typeof updated === "object" && "latest_verification_id" in updated && "referral_updated_at" in updated && (typeof updated.latest_verification_id === "string" || updated.latest_verification_id === null) && typeof updated.referral_updated_at === "string") {
        setBaseline({ latest: updated.latest_verification_id, updated: updated.referral_updated_at });
      }
      status.show("Availability verification added.");
    } catch (caught) {
      const invalidFields = timingBackendErrors(caught);
      setErrors(invalidFields); focusTimingError("verification-timing", draft, invalidFields);
      if (caught instanceof CompassApiError && readApiErrorCode(caught.body) === "referral_timing_changed") {
        setReviewRequired(true); setError("The Referral or verified availability changed. Your input is kept. Review the latest information above.");
        await onRefresh();
      } else if (!(caught instanceof CompassApiError) || caught.status >= 500 || caught.status === 408) {
        setReviewRequired(true); setError("Couldn't confirm whether verification was added. Your input is kept. Review the refreshed history before adding another record.");
        await onRefresh();
      } else if (caught.status === 403 || caught.status === 401 || caught.status === 404) {
        setError("You can't add verification to this Referral right now."); await onRefresh();
      } else {
        setError("Couldn't add verification. Check the information and try again.");
      }
    } finally { busy.current = false; intent.current = null; mutation.reset(); }
  }

  return <form className="space-y-4" noValidate onSubmit={submit} aria-label="Verify Referral availability" aria-busy={mutation.isPending} autoComplete="off">
    <h3 className="text-sm font-semibold text-brand">Add availability verification</h3>
    {changed ? <Notice tone="warning" action={<Button type="button" variant="secondary" disabled={unavailable || mutation.isPending} onClick={() => { setBaseline({ latest: facts.latest_verification_id, updated: facts.referral_updated_at }); setReviewRequired(false); setError(""); }}>Use latest details</Button>}>Review the latest Referral and verified availability above. Your input is kept; adding a record requires this review.</Notice> : null}
    <TimingEditor prefix="verification-timing" draft={draft} onChange={setDraft} errors={errors} verification disabled={mutation.isPending} />
    <div><Label htmlFor="verification-timing-confirmation_source">Confirmation source</Label><Select className="mt-2" id="verification-timing-confirmation_source" value={source} onChange={event => setSource(Object.values(ReferralTimingSource).find(value => value === event.target.value) ?? "")} disabled={mutation.isPending} aria-invalid={!!errors.confirmation_source} aria-describedby={errors.confirmation_source ? "verification-source-error" : undefined}><option value="">Choose a confirmation source</option>{Object.values(ReferralTimingSource).map(value => <option key={value} value={value}>{confirmationSourceLabels[value]}</option>)}</Select>{errors.confirmation_source ? <p id="verification-source-error" className="mt-1 text-sm text-danger">{errors.confirmation_source}</p> : null}</div>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <Button type="submit" disabled={mutation.isPending || unavailable || changed}>{mutation.isPending ? "Adding verification…" : "Add verification"}</Button>
    <ActionStatus status={status.status} onDismiss={status.dismiss} />
  </form>;
}
