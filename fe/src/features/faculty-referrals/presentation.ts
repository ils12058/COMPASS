import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

export function facultyReferralError(error: unknown, operation: "confirm" | "submit" | "read") {
  if (!(error instanceof CompassApiError)) return operation === "submit"
    ? "We could not confirm whether your referral was submitted. Keep this page open and retry the same submission deliberately."
    : "This request could not be completed. Try again when your connection is available.";
  const code = readApiErrorCode(error.body);
  if (error.status === 401) return "Your session needs to be checked. No request will be repeated automatically.";
  if (error.status === 403 && operation === "read") return "Your submitted referrals are not available for this account right now.";
  if (error.status === 403) return code?.startsWith("faculty_referral_")
    ? "Digital Referrals are not available for your account right now. Your input is still on this page."
    : "This request was not permitted. Your input is still on this page; try again only after resolving access.";
  if (error.status === 429) {
    const seconds = Number(error.headers["retry-after"]);
    return Number.isFinite(seconds) && seconds > 0
      ? `Too many confirmation attempts. Wait ${Math.ceil(seconds)} seconds before trying again.`
      : "Too many confirmation attempts. Wait before trying again.";
  }
  if (error.status === 503 && operation === "confirm") return "Student confirmation is temporarily unavailable. Keep the exact ID and try again later.";
  if (error.status === 404) return "This referral is not available. Return to My Referrals.";
  if (code === "faculty_referral_student_unavailable") return "Confirm the Student again before preparing a new submission. Your referral information is preserved.";
  if (error.status === 409) return "This submission could not be confirmed because it conflicts with the current record or form. Check My Referrals before deliberately starting a new submission.";
  if (error.status === 422) return "Check the form information. Your input is preserved.";
  return operation === "submit"
    ? "We could not confirm whether your referral was submitted. Keep this page open and retry the same submission deliberately."
    : "The request could not be completed. Try again later.";
}

export function uncertainSubmission(error: unknown) {
  return !(error instanceof CompassApiError) || error.status >= 500 || error.status === 408;
}

export function confirmationRetryDeadline(error: unknown, now = Date.now()) {
  if (!(error instanceof CompassApiError) || error.status !== 429) return null;
  const raw = error.headers["retry-after"];
  const seconds = Number(raw);
  if (raw && Number.isFinite(seconds) && seconds > 0) return new Date(now + seconds * 1000).toISOString();
  const date = raw ? Date.parse(raw) : Number.NaN;
  return Number.isFinite(date) && date > now ? new Date(date).toISOString() : null;
}
