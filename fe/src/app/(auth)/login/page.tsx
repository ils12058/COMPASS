import type { Metadata } from "next";

import { LoginScreen } from "@/features/auth/login/login-screen";
import { safePortalDestination } from "@/features/auth/utils/redirect";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  const requested = Array.isArray(next) ? next[0] : next;
  return <LoginScreen nextPath={safePortalDestination(requested)} />;
}
