import type { Metadata } from "next";

import { AuthSurface } from "@/features/auth/components/auth-surface";
import { MandatoryTotpSetup } from "@/features/auth/mfa/mandatory-totp-setup";
import { safePortalDestination } from "@/features/auth/utils/redirect";

export const metadata: Metadata = { title: "Set up authenticator" };

export default async function SetupAuthenticatorPage({ searchParams }: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  const nextPath = safePortalDestination(Array.isArray(next) ? next[0] : next);
  return (
    <AuthSurface size="wide">
      <MandatoryTotpSetup restartDestination={nextPath} />
    </AuthSurface>
  );
}
