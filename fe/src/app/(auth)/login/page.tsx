import type { Metadata } from "next";

import { AuthSurface } from "@/features/auth/components/auth-surface";
import { LoginScreen } from "@/features/auth/login/login-screen";
import { safePortalDestination } from "@/features/auth/utils/redirect";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[]; email_changed?: string | string[] }>;
}) {
  const { next, email_changed } = await searchParams;
  const requested = Array.isArray(next) ? next[0] : next;
  return (
    <AuthSurface>
      <LoginScreen nextPath={safePortalDestination(requested)} emailChanged={email_changed === "1"} />
    </AuthSurface>
  );
}
