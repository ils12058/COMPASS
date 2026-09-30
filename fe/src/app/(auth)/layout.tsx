import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AuthFlowProvider } from "@/features/auth/components/auth-flow-context";
import { AuthShell } from "@/features/auth/components/auth-shell";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <AuthFlowProvider>
      <AuthShell>{children}</AuthShell>
    </AuthFlowProvider>
  );
}
