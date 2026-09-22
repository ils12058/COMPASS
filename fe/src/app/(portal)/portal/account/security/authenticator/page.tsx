import type { Metadata } from "next";

import { AuthenticatorPage } from "@/features/account/security/authenticator/authenticator-page";

export const metadata: Metadata = { title: "Authenticator | COMPASS" };

export default function Page() {
  return <AuthenticatorPage />;
}
