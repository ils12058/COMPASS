import type { Metadata } from "next";

import { SessionsPage } from "@/features/account/security/sessions/sessions-page";

export const metadata: Metadata = { title: "Sessions and trusted browsers" };

export default function Page() {
  return <SessionsPage />;
}
