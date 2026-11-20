import type { Metadata } from "next";
import { AuthSurface } from "@/features/auth/components/auth-surface";
import { RecoveryLink } from "@/features/auth/password/recovery-link";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Recover your account", referrer: "no-referrer", robots: { index: false, follow: false } };

export default function AccountRecoveryPage() {
  return <AuthSurface size="wide"><RecoveryLink /></AuthSurface>;
}
