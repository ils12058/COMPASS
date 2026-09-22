import type { Metadata } from "next";

import { PasswordAccess } from "@/features/auth/password/password-access";

export const metadata: Metadata = { title: "Set up or reset password" };

export default function PasswordPage() {
  return <PasswordAccess />;
}
