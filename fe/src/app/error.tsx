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
      code="Something went wrong"
      title="COMPASS couldn’t open this page."
      description="Try again, or return to the COMPASS home page."
      requestReference={getApiRequestReference(error)}
      primaryAction={<Button onClick={reset}>Try again</Button>}
    />
  );
}
