"use client";

import { Button } from "@/components/ui/button";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { getApiRequestReference } from "@/lib/api/request-reference";

export default function AuthError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <AuthShell
      title="We couldn’t open sign-in"
      description="Please try again. Your account details have not been changed."
    >
      <div className="space-y-5">
        <p className="text-sm leading-6 text-muted-foreground">
          {getApiRequestReference(error)
            ? `Reference: ${getApiRequestReference(error)}`
            : "If this keeps happening, try again in a moment or return to COMPASS."}
        </p>
        <Button className="w-full" size="lg" onClick={reset}>
          Try again
        </Button>
      </div>
    </AuthShell>
  );
}
