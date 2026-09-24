import type { UserSummary } from "@/lib/api/generated/model";

export type FeedbackAccess = {
  isStudent: boolean;
  canSubmitCustomerFeedback: boolean;
  canSubmitCsm: boolean;
  canViewCustomerFeedback: boolean;
  canViewCsm: boolean;
  hasWorkspace: boolean;
};

export function getFeedbackAccess(user: UserSummary): FeedbackAccess {
  const isStudent = user.role === "STUDENT";
  const canSubmitCustomerFeedback =
    isStudent && user.capabilities.includes("feedback.submit_customer_feedback");
  const canSubmitCsm =
    isStudent && user.capabilities.includes("feedback.submit_csm");
  const canViewCustomerFeedback = user.capabilities.includes(
    "feedback.view_customer_feedback",
  );
  const canViewCsm = user.capabilities.includes("feedback.view_csm");

  return {
    isStudent,
    canSubmitCustomerFeedback,
    canSubmitCsm,
    canViewCustomerFeedback,
    canViewCsm,
    hasWorkspace:
      canSubmitCustomerFeedback ||
      canSubmitCsm ||
      canViewCustomerFeedback ||
      canViewCsm,
  };
}
