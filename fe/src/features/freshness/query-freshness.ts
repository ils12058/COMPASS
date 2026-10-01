import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

export function isSessionEndedError(error: unknown): error is CompassApiError {
  return error instanceof CompassApiError && error.status === 401;
}

export function isAuthorityError(error: unknown): error is CompassApiError {
  return error instanceof CompassApiError && error.status === 403;
}

export function isMutationAuthorityError(error: unknown): boolean {
  if (!isAuthorityError(error)) return false;
  const code = readApiErrorCode(error.body);
  return code !== "csrf_failed" && code !== "recent_mfa_required";
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
