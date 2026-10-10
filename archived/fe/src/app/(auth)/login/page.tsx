import { Suspense } from "react";

import { LoginScreen } from "@/features/auth/login/login-screen";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center px-5">
          <p role="status" className="text-sm text-muted-foreground">
            Preparing sign-in…
          </p>
        </main>
      }
    >
      <LoginScreen />
    </Suspense>
  );
}
