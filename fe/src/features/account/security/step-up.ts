import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

// What a retained strong-auth action needs before it can proceed (see backend step_up.py):
// "verify" — an authenticator is set up but was not verified recently, so a current code works;
// "setup" — the account has no authenticator, so there is no code to ask for.
export type StepUpRequirement = "verify" | "setup";

export const AUTHENTICATOR_SETUP_HREF = "/portal/account/security/authenticator";

export function stepUpRequirement(error: unknown): StepUpRequirement | null {
  if (!(error instanceof CompassApiError)) return null;
  const code = readApiErrorCode(error.body);
  if (code === "recent_mfa_required") return "verify";
  if (code === "mfa_setup_required") return "setup";
  return null;
}

// The status line a feature shows while the step-up dialog is open.
export function stepUpNotice(requirement: StepUpRequirement): string {
  return requirement === "setup"
    ? "This action needs an authenticator. Set one up in Security, then try again."
    : "Verify your authenticator, then submit the action again.";
}
