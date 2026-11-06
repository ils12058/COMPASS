import type { FacultyReferralAvailability, UserSummary } from "@/lib/api/generated/model";

export const facultyReferralsPath = "/portal/faculty/referrals";
export const facultySubmitPath = `${facultyReferralsPath}/new`;

export function facultyReferralAccess(user: UserSummary) {
  const faculty = user.role === "FACULTY";
  const read = faculty && user.capabilities.includes("referrals.view_submitted_self");
  // The Referral page only links to Messages; it never sends there.
  return {
    read,
    submit: read && user.capabilities.includes("referrals.submit_self"),
    message: read && user.capabilities.includes("guidance_messages.referral_manage_self"),
  };
}

export function facultySubmissionAvailable(value?: FacultyReferralAvailability) {
  return value?.can_confirm_student === true && value.can_submit_referral === true;
}
