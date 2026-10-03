import type { Metadata } from "next";

import { AuthSurface } from "@/features/auth/components/auth-surface";
import { MandatoryTotpSetup } from "@/features/auth/mfa/mandatory-totp-setup";

export const metadata: Metadata = { title: "Set up authenticator" };

export default function SetupAuthenticatorPage() {
  return (
    <AuthSurface size="wide">
      <MandatoryTotpSetup />
    </AuthSurface>
  );
}
