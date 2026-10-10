import type { Metadata } from "next";

import { AuthSurface } from "@/features/auth/components/auth-surface";
import { PasswordAccess } from "@/features/auth/password/password-access";

export const metadata: Metadata = { title: "Set up or reset password" };

export default function PasswordPage() {
  return (
    <AuthSurface size="wide">
      <PasswordAccess />
    </AuthSurface>
  );
}
