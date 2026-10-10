import { Suspense } from "react";

import { LoginScreen } from "@/features/auth/login/login-screen";

function LoginFallback() {
  return (
    <main className="grid min-h-screen place-items-center bg-[var(--compass-body)] p-6">
      <p className="text-sm text-muted-foreground" role="status">
        Preparing sign-in…
      </p>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginScreen />
    </Suspense>
  );
}
