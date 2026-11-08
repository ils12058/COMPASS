import type { GuidanceThreadResponse, UserSummary } from "@/lib/api/generated/model";
import type { GuidanceViewer } from "./guidance-messages-presentation";

// Presentation only (ADR-102). The API decides every thread: College scope, supervision, Head
// fallback and exact Counseling participation are never repeated here. A Student reads their own
// conversations; Counselors and Guidance Office Assistant read the ones their workload allows; a
// Faculty member reads the Guidance Office inquiries they wrote and the referral conversations
// they started. IT Admin, Institutional Officers, Head and DPO designations add nothing.
export type GuidanceMessagesAccess = {
  isStudent: boolean;
  isStaff: boolean;
  isFaculty: boolean;
  /** Which side of the conversation the reader is on, for every viewer-aware label. */
  viewer: GuidanceViewer;
  /** Student: may open the workspace for their own conversations. */
  canViewSelf: boolean;
  /** Student: may write to the Guidance Office or a Counseling relationship. */
  canManageSelf: boolean;
  /** Counselor or Guidance Office Assistant: may open the workspace for their workload. */
  canViewStaff: boolean;
  /** Counselor or Guidance Office Assistant: may write, start Office conversations, resolve and reopen. */
  canManageStaff: boolean;
  /** Faculty: may open the workspace for their own Guidance Office inquiries. */
  canViewInquirySelf: boolean;
  /** Faculty: may write, resolve and reopen their own inquiries. */
  canManageInquirySelf: boolean;
  /** Faculty: may open the workspace for referral conversations they started. */
  canViewReferralSelf: boolean;
  /** Faculty: may write to the referral conversations of their own submissions. */
  canManageReferralSelf: boolean;
  /** Staff: may reply to referral conversations inside their current Referral scope. */
  canManageReferralStaff: boolean;
  /** Counselor: may open the workspace for their direct Counselor conversations. */
  canViewDirect: boolean;
  /** Counselor: may start and reply to direct Counselor conversations. */
  canManageDirect: boolean;
  /** Counselor: may read a case-coordination conversation on a live coverage grant they participate in. */
  canViewCaseCoordination: boolean;
  /** Counselor: may start and reply to case-coordination conversations on their live grants. */
  canManageCaseCoordination: boolean;
  /** Staff with the intake designation: receive and answer Faculty inquiries. */
  canIntake: boolean;
  hasWorkspace: boolean;
  /** Writing a Message, and marking a conversation read, need manage authority. */
  canWrite: boolean;
  /** May start a conversation: Students their own, staff an Office thread, Faculty an inquiry. */
  canStart: boolean;
  /** Staff who write operational Messages may insert shared Message templates (ADR-104). */
  canUseTemplates: boolean;
  /** Creates, edits, archives and restores the shared templates. */
  canManageTemplates: boolean;
};

export function getGuidanceMessagesAccess(user: UserSummary): GuidanceMessagesAccess {
  const isStudent = user.role === "STUDENT";
  const isStaff = user.role === "COUNSELOR" || user.role === "GUIDANCE_OFFICE_ASSISTANT";
  const isFaculty = user.role === "FACULTY";
  const canViewSelf = isStudent && user.capabilities.includes("guidance_messages.view_self");
  const canManageSelf = canViewSelf && user.capabilities.includes("guidance_messages.manage_self");
  const canViewStaff = isStaff && user.capabilities.includes("guidance_messages.view");
  const canManageStaff = canViewStaff && user.capabilities.includes("guidance_messages.manage");
  const canViewInquirySelf =
    isFaculty && user.capabilities.includes("guidance_messages.inquiry_view_self");
  const canManageInquirySelf =
    canViewInquirySelf && user.capabilities.includes("guidance_messages.inquiry_manage_self");
  const canViewReferralSelf =
    isFaculty && user.capabilities.includes("guidance_messages.referral_view_self");
  const canManageReferralSelf =
    canViewReferralSelf && user.capabilities.includes("guidance_messages.referral_manage_self");
  const canManageReferralStaff =
    isStaff &&
    user.capabilities.includes("guidance_messages.manage") &&
    user.capabilities.includes("referrals.manage");
  const isCounselor = user.role === "COUNSELOR";
  // The narrow direct capability depends on broad `guidance_messages.view`; the server resolves
  // that dependency, and the presentation repeats it so a partial payload cannot over-grant.
  const canViewDirect =
    isCounselor &&
    user.capabilities.includes("guidance_messages.view") &&
    user.capabilities.includes("guidance_messages.counselor_direct.view");
  const canManageDirect =
    canViewDirect && user.capabilities.includes("guidance_messages.counselor_direct.manage");
  // Case coordination repeats the same broad-view dependency. Neither narrow capability is
  // authority on its own: the server's live Counseling predicate decides whether anything exists.
  const canViewCaseCoordination =
    isCounselor &&
    user.capabilities.includes("guidance_messages.view") &&
    user.capabilities.includes("guidance_messages.case_coordination.view");
  const canManageCaseCoordination =
    canViewCaseCoordination &&
    user.capabilities.includes("guidance_messages.case_coordination.manage");
  const canIntake = isStaff && user.capabilities.includes("guidance_messages.intake");
  const canManageTemplates =
    canManageStaff && user.capabilities.includes("guidance_messages.templates.manage");

  return {
    isStudent,
    isStaff,
    isFaculty,
    viewer: isStudent ? "student" : isFaculty ? "faculty" : "staff",
    canViewSelf,
    canManageSelf,
    canViewStaff,
    canManageStaff,
    canViewInquirySelf,
    canManageInquirySelf,
    canViewReferralSelf,
    canManageReferralSelf,
    canManageReferralStaff,
    canViewDirect,
    canManageDirect,
    canViewCaseCoordination,
    canManageCaseCoordination,
    canIntake,
    hasWorkspace:
      canViewSelf ||
      canViewStaff ||
      canViewInquirySelf ||
      canViewReferralSelf ||
      canViewDirect ||
      canViewCaseCoordination ||
      canIntake,
    canWrite:
      canManageSelf ||
      canManageStaff ||
      canManageInquirySelf ||
      canManageReferralSelf ||
      canManageDirect ||
      canManageCaseCoordination ||
      canIntake,
    // A referral conversation starts contextually from the Referral, not from the generic New
    // message chooser; case coordination is contextual to its coverage grant in the same way.
    canStart: canManageSelf || canManageStaff || canManageInquirySelf || canManageDirect,
    canUseTemplates: canManageStaff,
    canManageTemplates,
  };
}

/** The composer's template option: staff who write operational Messages; never Students. */
export function messageTemplatesFor(access: GuidanceMessagesAccess): { canManage: boolean } | null {
  return access.canUseTemplates ? { canManage: access.canManageTemplates } : null;
}

/** Direct and case threads are written only with their narrow capability; other kinds use the workspace gate. */
export function canWriteThread(
  thread: GuidanceThreadResponse,
  access: GuidanceMessagesAccess,
): boolean {
  if (thread.kind === "COUNSELOR_DIRECT") return access.canManageDirect;
  if (thread.kind === "COUNSELOR_CASE_COORDINATION") return access.canManageCaseCoordination;
  return access.canWrite;
}
