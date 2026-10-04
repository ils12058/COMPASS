import {
  privacyErrorMessage,
} from "@/features/privacy-governance/privacy-governance-errors";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import type {
  MyNoticeResponse,
  PrivacyGovernanceListMyNoticesParams,
} from "@/lib/api/generated/model";

export const ACKNOWLEDGMENT_HELP =
  "Acknowledgment records that you have seen this notice. It is not consent to all data processing.";

// The portal asks for one notice at a time: the first current notice that still asks this account
// for an acknowledgment. Account › Privacy keeps the full list and history.
export const PENDING_NOTICE_PARAMS: PrivacyGovernanceListMyNoticesParams = {
  pending_acknowledgment: true,
  page: 1,
  page_size: 1,
};

// Checked on each item as well, so a response that ignored the pending filter can never bring
// back a notice that was already acknowledged or that does not ask for acknowledgment.
export function nextPendingNotice(
  items: readonly MyNoticeResponse[] | undefined,
): MyNoticeResponse | undefined {
  return items?.find((item) => item.requires_acknowledgment && !item.acknowledged);
}

export function acknowledgeErrorMessage(caught: unknown): string {
  if (
    caught instanceof CompassApiError &&
    readApiErrorCode(caught.body) === "permission_denied"
  ) {
    return "Your account cannot acknowledge notices right now.";
  }
  return privacyErrorMessage(caught, "The notice could not be acknowledged.");
}
