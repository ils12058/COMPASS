import { CompassApiError } from "@/lib/api/client";
import { getStructuredApiRequestId } from "@/lib/api/error-payload";

export function getApiRequestReference(error: unknown): string | null {
  if (!(error instanceof CompassApiError)) {
    return null;
  }

  return getStructuredApiRequestId(error.data);
}
