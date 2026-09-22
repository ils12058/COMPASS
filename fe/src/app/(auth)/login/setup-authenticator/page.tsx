import type { Metadata } from "next";

import { MandatoryTotpSetup } from "@/features/auth/mfa/mandatory-totp-setup";

export const metadata: Metadata = { title: "Set up authenticator" };

export default function SetupAuthenticatorPage() {
  return <MandatoryTotpSetup />;
}
