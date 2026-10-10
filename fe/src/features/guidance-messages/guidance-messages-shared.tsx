import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

// Thread IDs are opaque UUIDs; anything else in the URL is not a conversation and is never sent.
const THREAD_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isThreadId(value: string): boolean {
  return THREAD_ID.test(value);
}

export function errorStatus(error: unknown): number | null {
  return error instanceof CompassApiError ? error.status : null;
}

/**
 * The reader cannot see this conversation, or no longer can: signed out, access refused, or a
 * concealed thread. Nothing previously loaded for it may stay on screen.
 */
export function isConcealingError(error: unknown): boolean {
  const status = errorStatus(error);
  return status === 401 || status === 403 || status === 404 || status === 422;
}

export function isContentUnavailable(error: unknown): boolean {
  return (
    error instanceof CompassApiError &&
    error.status === 503 &&
    readApiErrorCode(error.body) === "guidance_message_content_unavailable"
  );
}

export const CONVERSATION_HEADING_ID = "guidance-conversation-heading";
export const MESSAGES_HEADING_ID = "guidance-messages-heading";

export function DirectorySkeleton() {
  return (
    <LoadingRegion label="Loading conversations" className="divide-y divide-border">
      {Array.from({ length: 6 }, (_, index) => (
        <div key={index} className="space-y-2 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <Skeleton className="h-4 w-2/5" />
            <Skeleton className="h-3 w-12" />
          </div>
          <Skeleton className="h-3 w-1/3" />
        </div>
      ))}
    </LoadingRegion>
  );
}

export function ConversationSkeleton() {
  return (
    <LoadingRegion label="Loading messages" className="space-y-4 px-4 py-4">
      {[0, 1, 2, 3].map((index) => (
        <div key={index} className={index % 2 ? "flex flex-col items-end" : "flex flex-col items-start"}>
          <Skeleton className="h-3 w-24" />
          <Skeleton className={index % 2 ? "mt-1.5 h-12 w-1/2" : "mt-1.5 h-16 w-3/5"} />
        </div>
      ))}
    </LoadingRegion>
  );
}
