import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";
import { uncertainGoodMoralMutation } from "./good-moral-shared";

export function assistedCreationError(error: unknown): string {
  if (uncertainGoodMoralMutation(error)) return "The result could not be confirmed. Retry the same request to check whether it was received. Keep these details unchanged.";
  if (!(error instanceof CompassApiError)) return "The request could not be started.";
  switch (readApiErrorCode(error.body)) {
    case "good_moral_not_found": return "The Student was not found or is no longer eligible. Search for an eligible Student again.";
    case "good_moral_inventory_required": return "The Student must submit their Individual Inventory for the current Academic Year before this request can proceed.";
    case "good_moral_exit_interview_required": return "The Student must submit their required graduation Exit Interview before this request can proceed.";
    case "good_moral_affiliation_required": return "The Student needs a current active College affiliation before this request can proceed.";
    case "current_student_required":
    case "graduated_student_required": return "The Student’s lifecycle has changed. Search and select the Student again to review the applicable request.";
    case "good_moral_conflict": return "This Student already has a pending Good Moral request. Open it in the request queue.";
    case "idempotency_key_conflict": return "This attempt no longer matches its original request. Review the request queue before starting another request.";
    case "permission_denied": return "You no longer have permission to start this request.";
    case "invalid_good_moral_request": return readApiErrorMessage(error.body) ?? "Check the request details and try again.";
    default: return "The Good Moral request could not be started. Review the details and try again.";
  }
}
