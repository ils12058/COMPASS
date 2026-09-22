"use client";

import { Button } from "@/components/ui/button";
import { SystemErrorPage } from "@/features/system/components/system-error-page";
import { getApiRequestReference } from "@/lib/api/request-reference";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <SystemErrorPage
      code="We hit a snag"
      title="We couldn’t open this page."
      description="Please try again, or go back to COMPASS."
      requestReference={getApiRequestReference(error)}
      primaryAction={<Button onClick={reset}>Try again</Button>}
    />
  );
}
