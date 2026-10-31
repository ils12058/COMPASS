"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { boundaryDelay, useServerBoundary } from "@/features/freshness/use-server-boundary";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { referralsFacultyConfirmStudent, referralsFacultySubmit, getReferralsFacultyListMineQueryKey } from "@/lib/api/generated/referrals/referrals";
import type { FacultyReferralSubmitRequest, FacultyStudentConfirmationResponse, FacultyReferralSubmissionResponse } from "@/lib/api/generated/model";
import { confirmationRetryDeadline, facultyReferralError, uncertainSubmission } from "./presentation";

type IntendedSubmission = { key: string; body: FacultyReferralSubmitRequest };
type Confirmed = { response: FacultyStudentConfirmationResponse; serverDate?: string; receivedAt: number; deadline: number };

export function validateReferralFields(identifier: string, course: string, reason: string) {
  return {
    identifier: !identifier.trim() ? "Enter the exact institutional ID." : identifier.length > 64 ? "Institutional ID must be 64 characters or fewer." : "",
    course: !course.trim() ? "Enter the Course/Year/Block." : course.length > 255 ? "Course/Year/Block must be 255 characters or fewer." : "",
    reason: !reason.trim() ? "Enter the reason for referral." : reason.length > 10000 ? "Referral reason must be 10,000 characters or fewer." : "",
  };
}

export function useFacultySubmission({ available, onPolicyChange }: { available: boolean; onPolicyChange: () => void }) {
  const client = useQueryClient();
  const { confirmDiscard } = useUnsavedNavigation();
  const [identifier, setIdentifier] = useState("");
  const [course, setCourse] = useState("");
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState<Confirmed | null>(null);
  const [expired, setExpired] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState({ identifier: "", course: "", reason: "" });
  const [cooldown, setCooldown] = useState<string | null>(null);
  const [result, setResult] = useState<FacultyReferralSubmissionResponse | null>(null);
  const intent = useRef<IntendedSubmission | null>(null);
  const busy = useRef(false);
  const dirty = !!(identifier || course || reason);
  useUnsavedChangesGuard({ dirty, message: uncertain
    ? "The submission outcome is not confirmed. Check My Referrals before starting another. Discard this draft and its retry information?"
    : "Discard your unsaved referral? Its confidential information is kept only on this page." });
  useServerBoundary({ boundary: confirmed?.response.expires_at, serverDate: confirmed?.serverDate, receivedAt: confirmed?.receivedAt, onBoundary: () => setExpired(true) });
  useServerBoundary({ boundary: cooldown, onBoundary: () => setCooldown(null) });

  // No mutation variables or returned payloads enter MutationCache: sensitive draft/ticket stay
  // in this component's closure only. The generated functions still own all wire contracts.
  const confirmation = useMutation({ retry: false, gcTime: 0, mutationFn: async () => {
    const reply = await referralsFacultyConfirmStudent({ institutional_id: identifier });
    if (reply.data.confirmed && reply.data.confirmation && reply.data.student && reply.data.expires_at) {
      const receivedAt = Date.now();
      const delay = boundaryDelay(reply.data.expires_at, reply.headers.date, receivedAt);
      if (delay === null || delay <= 0) { setExpired(true); setError("Confirm the Student again; this confirmation has expired."); return; }
      setConfirmed({ response: reply.data, serverDate: reply.headers.date, receivedAt, deadline: receivedAt + delay });
      setExpired(false);
    } else {
      setConfirmed(null);
      setError("The Student could not be confirmed. Check the exact institutional ID or contact the Guidance and Counseling Office through your usual institutional channel.");
    }
  } });
  const submission = useMutation({ retry: false, gcTime: 0, mutationFn: async () => {
    const intended = intent.current;
    if (!intended) throw new Error("Missing intended submission");
    const reply = await referralsFacultySubmit(intended.body, { headers: { "Idempotency-Key": intended.key } });
    if ((reply.status !== 200 && reply.status !== 201) || !["SUBMITTED", "RECEIVED_BY_GCO", "ADMINISTRATIVELY_CLOSED"].includes(reply.data.state)) throw new Error("Unconfirmed submission result");
    setResult(reply.data);
    setIdentifier(""); setCourse(""); setReason(""); setConfirmed(null);
    intent.current = null; setUncertain(false); setReviewing(false); setError("");
    void client.invalidateQueries({ queryKey: getReferralsFacultyListMineQueryKey() });
  } });

  const pending = confirmation.isPending || submission.isPending;
  async function confirmStudent() {
    if (busy.current || !available || cooldown || uncertain) return;
    const invalid = validateReferralFields(identifier, course, reason).identifier;
    setErrors((old) => ({ ...old, identifier: invalid })); setError("");
    if (invalid) { document.getElementById("faculty-student-id")?.focus(); return; }
    busy.current = true; setConfirmed(null); setExpired(false); intent.current = null;
    try { await confirmation.mutateAsync(); }
    catch (caught) { setError(facultyReferralError(caught, "confirm")); setCooldown(confirmationRetryDeadline(caught)); if (caught instanceof CompassApiError && caught.status === 403) onPolicyChange(); }
    finally { busy.current = false; confirmation.reset(); }
  }
  function review() {
    if (busy.current || !available || uncertain) return;
    const invalid = validateReferralFields(identifier, course, reason);
    setErrors(invalid); setError("");
    const first = invalid.identifier ? "faculty-student-id" : invalid.course ? "faculty-course" : invalid.reason ? "faculty-reason" : null;
    if (first) { document.getElementById(first)?.focus(); return; }
    if (!confirmed?.response.confirmation || expired || Date.now() >= confirmed.deadline) { setExpired(true); setError("Confirm the Student again before reviewing your referral."); return; }
    intent.current = null; setReviewing(true);
  }
  async function submit() {
    if (busy.current || !available || !reviewing) return;
    if (!intent.current) {
      if (!confirmed?.response.confirmation || expired || Date.now() >= confirmed.deadline) { setExpired(true); setError("Confirm the Student again before preparing a new submission."); return; }
      intent.current = { key: crypto.randomUUID(), body: { confirmation: confirmed.response.confirmation, course_year_block: course, reason } };
    }
    busy.current = true; setError("");
    try { await submission.mutateAsync(); }
    catch (caught) {
      setError(facultyReferralError(caught, "submit")); setUncertain(uncertainSubmission(caught));
      if (caught instanceof CompassApiError && readApiErrorCode(caught.body) === "faculty_referral_student_unavailable") { setExpired(true); }
      if (caught instanceof CompassApiError && caught.status === 403) onPolicyChange();
    } finally { busy.current = false; submission.reset(); }
  }
  function discard() {
    if (busy.current || (dirty && !confirmDiscard())) return;
    setIdentifier(""); setCourse(""); setReason(""); setConfirmed(null); setError(""); setErrors({ identifier: "", course: "", reason: "" });
    setReviewing(false); setUncertain(false); setExpired(false); intent.current = null;
  }
  function edit() {
    if (busy.current || uncertain) return;
    intent.current = null; setReviewing(false); setError("");
    requestAnimationFrame(() => document.getElementById("faculty-student-id")?.focus());
  }
  return { identifier, course, reason, confirmed: confirmed?.response, expired, reviewing, uncertain, error, errors, cooldown, result, pending, dirty,
    confirming: confirmation.isPending, submitting: submission.isPending,
    changeIdentifier(value: string) { if (busy.current || uncertain) return; setIdentifier(value); setConfirmed(null); setExpired(false); intent.current = null; },
    changeCourse: setCourse, changeReason: setReason, confirmStudent, review, submit, discard, edit };
}
