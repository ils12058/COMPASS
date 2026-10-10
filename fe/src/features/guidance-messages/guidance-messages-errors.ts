import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { AccountChangedError } from "@/lib/query/account-ownership";

// What a failed Guidance Messages action means to the reader. Backend messages are not shown as
// they are: they name internal concepts ("Guidance thread"), and none of them carries content.

export type GuidanceSendContext = "thread" | "student-office" | "student-counseling" | "staff-office";

function status(error: unknown): number | null {
  return error instanceof CompassApiError ? error.status : null;
}

export function describeSendError(error: unknown, context: GuidanceSendContext): string {
  if (error instanceof AccountChangedError) return "The signed-in account changed, so this message was not shown here.";
  const code = status(error);
  if (code === null || code === 408) {
    return "Your message could not be confirmed because the connection to COMPASS failed.";
  }
  if (code === 503 && error instanceof CompassApiError && readApiErrorCode(error.body) === "guidance_message_content_unavailable") {
    return "Messages are temporarily unavailable, so your message could not be confirmed.";
  }
  if (code >= 500) return "COMPASS could not confirm your message.";
  if (code === 401) return "Your session needs to be checked again. Your message was not sent and is still here.";
  if (code === 403) return "Your account can no longer send this message. It was not sent.";
  if (code === 422) {
    return "Your message was not sent. It must contain text and be no longer than 4,000 characters.";
  }
  if (code === 429) return "Too many messages were sent in a short time. Wait a moment, then send it again.";
  if (code === 404) {
    if (context === "student-counseling") {
      return "This Counseling relationship can no longer receive messages. Your message was not sent; choose another recipient.";
    }
    if (context === "staff-office") {
      return "This Student is no longer in your workload. Your message was not sent; search again and choose another Student.";
    }
    return "This conversation is no longer available. Your message was not sent.";
  }
  if (code === 409) {
    if (context === "student-office") {
      return "The Guidance Office cannot receive messages from your account right now. Your message was not sent; try again later or visit the Guidance Office.";
    }
    if (context === "staff-office") {
      return "A Guidance Office conversation cannot be started for this Student right now because their College has no available Guidance Office routing. Your message was not sent.";
    }
    return "This conversation is resolved, so your message was not sent. Your text is still here.";
  }
  return "Your message was not sent.";
}

export function describeStatusChangeError(error: unknown, action: "resolve" | "reopen"): string {
  const code = status(error);
  if (action === "reopen" && code === 409) {
    return "This conversation cannot be reopened because the Student already has an open Guidance Office conversation.";
  }
  if (code === 404 || code === 403) return "This conversation is no longer available to your account.";
  if (code === 401) return "Your session needs to be checked again before this conversation can change.";
  return action === "resolve"
    ? "The conversation could not be resolved. Try again."
    : "The conversation could not be reopened. Try again.";
}

export function describeOlderError(error: unknown): string {
  return status(error) === 503
    ? "Older messages are temporarily unavailable."
    : "Older messages could not be loaded. Try again.";
}

export function describeAssignError(error: unknown): string {
  if (error instanceof AccountChangedError) return "The signed-in account changed, so this conversation was not assigned here.";
  const code = status(error);
  if (code === 422) {
    return "The person you chose can no longer be assigned this conversation. The list was refreshed; choose someone else.";
  }
  if (code === 404 || code === 403) return "This conversation is no longer available to your account.";
  if (code === 401) return "Your session needs to be checked again before this conversation can be assigned.";
  return "The conversation could not be assigned. Try again.";
}
