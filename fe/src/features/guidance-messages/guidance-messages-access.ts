import type { UserSummary } from "@/lib/api/generated/model";
import type { GuidanceViewer } from "./guidance-messages-presentation";

// Presentation only (ADR-102). The API decides every thread: College scope, supervision, Head
// fallback and exact Counseling participation are never repeated here. A Student reads their own
// conversations; Counselors and Guidance Services Staff read the ones their workload allows; a
// Faculty member reads only the Guidance Office inquiries they wrote. IT Admin, Institutional
// Officers, Head and DPO designations add nothing.
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
  /** Counselor or Guidance Services Staff: may open the workspace for their workload. */
  canViewStaff: boolean;
  /** Counselor or Guidance Services Staff: may write, start Office conversations, resolve and reopen. */
  canManageStaff: boolean;
  /** Faculty: may open the workspace for their own Guidance Office inquiries. */
  canViewInquirySelf: boolean;
  /** Faculty: may write, resolve and reopen their own inquiries. */
  canManageInquirySelf: boolean;
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
  const isStaff = user.role === "COUNSELOR" || user.role === "GUIDANCE_SERVICES_STAFF";
  const isFaculty = user.role === "FACULTY";
  const canViewSelf = isStudent && user.capabilities.includes("guidance_messages.view_self");
  const canManageSelf = canViewSelf && user.capabilities.includes("guidance_messages.manage_self");
  const canViewStaff = isStaff && user.capabilities.includes("guidance_messages.view");
  const canManageStaff = canViewStaff && user.capabilities.includes("guidance_messages.manage");
  const canViewInquirySelf =
    isFaculty && user.capabilities.includes("guidance_messages.inquiry_view_self");
  const canManageInquirySelf =
    canViewInquirySelf && user.capabilities.includes("guidance_messages.inquiry_manage_self");
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
    canIntake,
    hasWorkspace: canViewSelf || canViewStaff || canViewInquirySelf || canIntake,
    canWrite: canManageSelf || canManageStaff || canManageInquirySelf || canIntake,
    canStart: canManageSelf || canManageStaff || canManageInquirySelf,
    canUseTemplates: canManageStaff,
    canManageTemplates,
  };
}

/** The composer's template option: staff who write operational Messages; never Students. */
export function messageTemplatesFor(access: GuidanceMessagesAccess): { canManage: boolean } | null {
  return access.canUseTemplates ? { canManage: access.canManageTemplates } : null;
}
