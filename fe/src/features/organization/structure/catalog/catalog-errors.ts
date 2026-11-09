import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

const messages: Record<string, string> = {
  permission_denied: "You don't have access to manage the organization catalog.",
  invalid_session: "Couldn't confirm your sign-in. Sign in again to continue.",
  mfa_setup_required: "Set up an authenticator in Account Security, then review this change again.",
  recent_mfa_required: "Verify your authenticator, then review the latest record before submitting again.",
  catalog_not_found: "This Catalog record is no longer available. Return to the structure and review the available records.",
  catalog_duplicate_code: "This code is already used in this Campus or College, even if the record is inactive. Choose another code.",
  catalog_stale_version: "This information was updated. Your input is preserved; review the latest saved values before submitting again.",
  catalog_inactive_parent: "The parent campus or college is inactive. Review the parent; it will not be activated automatically.",
  catalog_deactivation_blocked: "Linked records now prevent deactivation. Review the refreshed blockers before continuing.",
  catalog_policy_approval_required: "Active Programs need a classification and year levels. Review the Program settings before continuing.",
  catalog_pending_f4_policy_decision_required: "Pending Good Moral Certificate requests for current Students (F4) need an institutional decision before you change these Program settings. Contact the Guidance Office.",
  catalog_not_initialized: "Organization setup isn't ready. Contact the Guidance Office.",
  catalog_busy: "Another change is in progress. The latest details must be reviewed before a new attempt.",
  invalid_catalog_request: "Some Catalog values cannot be used. Review the fields and change note.",
  validation_error: "Review the required fields and Program settings before submitting again.",
};
export function catalogErrorCode(error: unknown) {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}
export function catalogErrorMessage(error: unknown) {
  const code = catalogErrorCode(error);
  return (code && messages[code]) || "Couldn't complete the change. Review the latest details before trying again.";
}
export function uncertainCatalogOutcome(error: unknown) {
  return !(error instanceof CompassApiError) || error.status === 408 || error.status >= 500;
}
