import type { Metadata } from "next";

import { AuthSurface } from "@/features/auth/components/auth-surface";
import { MfaVerification } from "@/features/auth/mfa/mfa-verification";
import { safePortalDestination } from "@/features/auth/utils/redirect";

export const metadata: Metadata = { title: "Verify sign in" };

export default async function VerifyLoginPage({ searchParams }: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  const nextPath = safePortalDestination(Array.isArray(next) ? next[0] : next);
  return (
    <AuthSurface>
      <MfaVerification restartDestination={nextPath} />
    </AuthSurface>
  );
}
