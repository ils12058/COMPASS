import type { Metadata } from "next";

import { PasswordChangePage } from "@/features/account/security/password/password-change-page";

export const metadata: Metadata = { title: "Change password | COMPASS" };

export default function Page() {
  return <PasswordChangePage />;
}
