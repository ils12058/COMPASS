import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

const messages: Record<string, string> = {
  csrf_failed: "Your security token expired. Please try again.",
  email_change_conflict: "That sign-in email is already in use or the pending request changed.",
  email_change_not_found: "The email change request is no longer available. Start again.",
  invalid_email_change_request: "The verification details could not be confirmed. Check the code or start again.",
  invalid_profile_photo: "Choose a valid JPEG, PNG, or WebP image.",
  mfa_already_enabled: "An authenticator is already enabled for this account.",
  mfa_failed: "The authenticator code could not be verified.",
  mfa_not_configured: "Set up an authenticator before continuing.",
  mfa_setup_required: "Set up an authenticator before continuing.",
  recent_mfa_required: "Recent authenticator verification is required. Verify and try again.",
  password_change_authentication_failed: "The current password could not be verified.",
  profile_photo_storage_unavailable: "The profile photo could not be updated right now. Your other profile information is still available.",
  profile_unavailable: "Your profile is temporarily unavailable. Please try again.",
  rate_limited: "Too many attempts. Please try again later.",
  security_unavailable: "This security operation is temporarily unavailable. Please try again.",
  security_verification_failed: "Security verification could not be completed. Please try again.",
  totp_step_up_required: "An authenticator is required for this action. Manage it from Security.",
};

export function accountErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function accountErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  if (code === "invalid_profile_request") return readApiErrorMessage(error.body) ?? fallback;
  return code ? (messages[code] ?? fallback) : fallback;
}
