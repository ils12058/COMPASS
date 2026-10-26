import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

const messages: Record<string, string> = {
  permission_denied: "Your Catalog management access is unavailable. Review your current access before continuing.",
  invalid_session: "Your sign-in could not be confirmed. Sign in again before continuing.",
  mfa_setup_required: "Set up an authenticator in Account Security, then review this change again.",
  recent_mfa_required: "Verify your authenticator, then review the latest record before submitting again.",
  catalog_not_found: "This Catalog record is no longer available. Return to the structure and review the available records.",
  catalog_duplicate_code: "This code is already reserved in this parent context, including inactive records. Review the code.",
  catalog_stale_version: "This record changed. Your input is preserved; review the latest saved values before submitting again.",
  catalog_inactive_parent: "The parent campus or college is inactive. Review the parent; it will not be activated automatically.",
  catalog_deactivation_blocked: "Linked records now prevent deactivation. Review the refreshed blockers before continuing.",
  catalog_policy_approval_required: "Activation requires a complete academic policy and active parent records. Review the institutional policy before continuing.",
  catalog_pending_f4_policy_decision_required: "Pending Good Moral F4 requests need an institutional decision before this Program policy can change. Contact the certificate owner for review.",
  catalog_not_initialized: "Catalog management is not ready. Ask the responsible administrator to review initialization.",
  catalog_busy: "Another change is in progress. The latest details must be reviewed before a new attempt.",
  invalid_catalog_request: "Some Catalog values cannot be used. Review the fields and institutional basis.",
  validation_error: "Review the required fields and academic policy before submitting again.",
};
export function catalogErrorCode(error: unknown) {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}
export function catalogErrorMessage(error: unknown) {
  const code = catalogErrorCode(error);
  return (code && messages[code]) || "The change could not be completed. Review the latest details before trying again.";
}
export function uncertainCatalogOutcome(error: unknown) {
  return !(error instanceof CompassApiError) || error.status === 408 || error.status >= 500;
}
