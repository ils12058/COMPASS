import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

export function isSessionEndedError(error: unknown): error is CompassApiError {
  return error instanceof CompassApiError && error.status === 401;
}

export function isAuthorityError(error: unknown): error is CompassApiError {
  return error instanceof CompassApiError && error.status === 403;
}

// A 403 that asks for a fresh CSRF token or a step-up is about this request, not a change to the
// account's access, so it does not trigger a session recheck.
const REQUEST_SCOPED_REFUSALS = new Set(["csrf_failed", "recent_mfa_required", "mfa_setup_required"]);

export function isMutationAuthorityError(error: unknown): boolean {
  if (!isAuthorityError(error)) return false;
  const code = readApiErrorCode(error.body);
  return !code || !REQUEST_SCOPED_REFUSALS.has(code);
}

export function isTransientRefreshError(error: unknown): boolean {
  if (!(error instanceof CompassApiError)) return error instanceof TypeError;
  return error.status === 408 || error.status === 429 || error.status >= 500;
}

export function canShowLastKnownData({
  data,
  error,
  isPlaceholderData = false,
}: {
  data?: unknown;
  error: unknown;
  isPlaceholderData?: boolean;
}): boolean {
  return data !== undefined && !isPlaceholderData && isTransientRefreshError(error);
}

export function safeQueryData<T>(query: {
  data?: T;
  error: unknown;
  isError: boolean;
  isPlaceholderData?: boolean;
}): T | undefined {
  return query.isError && !canShowLastKnownData(query) ? undefined : query.data;
}

export function shouldHideProtectedData(error: unknown): boolean {
  return isSessionEndedError(error) || isAuthorityError(error);
}
