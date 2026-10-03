import type { Metadata } from "next";

export const metadata: Metadata = { title: "Create Account" };

import { CreateAccount } from "@/features/accounts/create/create-account";

export default function Page() {
  return <CreateAccount />;
}
