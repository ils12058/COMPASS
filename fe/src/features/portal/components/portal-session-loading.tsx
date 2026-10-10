import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";

// Shown while the portal session is checked: by the portal layout before the client takes over,
// and by PortalBoundary while the session query is pending or being verified again.
export function PortalSessionLoading() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md items-center px-5">
      <LoadingRegion label="Checking your session…" className="w-full">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="mt-4 h-5 w-full" />
      </LoadingRegion>
    </main>
  );
}
