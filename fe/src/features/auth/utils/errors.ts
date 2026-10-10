import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

const ERROR_MESSAGES: Record<string, string> = {
  authentication_failed: "Invalid email or password.",
  csrf_failed: "Your security token expired. Please submit the form again.",
  mfa_enrollment_challenge_invalid: "Authenticator setup is no longer available. Restart sign in.",
  mfa_failed: "The verification code could not be verified.",
  password_challenge_invalid: "The security code could not be verified or is no longer valid.",
  rate_limited: "Too many authentication attempts. Please try again later.",
  security_unavailable: "Authentication is temporarily unavailable. Please try again.",
  security_verification_failed: "The security verification could not be completed.",
};

export function authErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return code ? (ERROR_MESSAGES[code] ?? fallback) : fallback;
}

export function passwordPolicyMessages(error: unknown): string[] {
  if (!(error instanceof CompassApiError) || readApiErrorCode(error.body) !== "password_policy_failed") {
    return [];
  }

  if (!error.body || typeof error.body !== "object" || !("error" in error.body)) return [];
  const detail = error.body.error;
  if (!detail || typeof detail !== "object" || !("details" in detail) || !Array.isArray(detail.details)) {
    return [];
  }

  return detail.details.flatMap((issue) => {
    if (!issue || typeof issue !== "object" || !("message" in issue)) return [];
    return typeof issue.message === "string" ? [issue.message] : [];
  });
}
