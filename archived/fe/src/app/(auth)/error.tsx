"use client";

import { Button } from "@/components/ui/button";
import { SystemErrorPage } from "@/features/system/components/system-error-page";
import { getApiRequestReference } from "@/lib/api/request-reference";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <SystemErrorPage
      code="Couldn’t load this page"
      title="We couldn’t load this right now."
      description="Try again. If the problem continues, return to the COMPASS home page."
      requestReference={getApiRequestReference(error)}
      primaryAction={<Button onClick={reset}>Try again</Button>}
    />
  );
}
