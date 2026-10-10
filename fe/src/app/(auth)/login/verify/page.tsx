import type { Metadata } from "next";

import { AuthSurface } from "@/features/auth/components/auth-surface";
import { MfaVerification } from "@/features/auth/mfa/mfa-verification";

export const metadata: Metadata = { title: "Verify sign in" };

export default function VerifyLoginPage() {
  return (
    <AuthSurface>
      <MfaVerification />
    </AuthSurface>
  );
}
