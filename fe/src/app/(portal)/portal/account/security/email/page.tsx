import type { Metadata } from "next";

import { EmailChangePage } from "@/features/account/security/email/email-change-page";

export const metadata: Metadata = { title: "Change email" };

export default function Page() {
  return <EmailChangePage />;
}
