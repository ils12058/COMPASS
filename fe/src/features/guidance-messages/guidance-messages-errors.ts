import {
  CASE_COORDINATION_ENDED_COPY,
  CASE_COORDINATION_UNAVAILABLE_COPY,
} from "@/features/guidance-messages/guidance-messages-presentation";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { AccountChangedError } from "@/lib/query/account-ownership";

// What a failed Guidance Messages action means to the reader. Backend messages are not shown as
// they are: they name internal concepts ("Guidance thread"), and none of them carries content.

export type GuidanceSendContext =
  | "thread"
  | "student-office"
  | "student-counseling"
  | "staff-office"
  | "counselor-direct"
  | "faculty-inquiry"
  | "referral-coordination"
  | "case-coordination";

function status(error: unknown): number | null {
  return error instanceof CompassApiError ? error.status : null;
}

export function describeSendError(error: unknown, context: GuidanceSendContext): string {
  if (error instanceof AccountChangedError) return "The signed-in account changed, so this message was not shown here.";
  const code = status(error);
  if (code === null || code === 408) {
    return "Couldn't confirm your message because the connection to COMPASS failed. Try again.";
  }
  if (code === 503 && error instanceof CompassApiError && readApiErrorCode(error.body) === "guidance_message_content_unavailable") {
    return "Couldn't confirm your message because Messages can't be opened right now. Try again.";
  }
  if (code >= 500) return "Couldn't confirm your message. Try again.";
  if (code === 401) return "Your session needs to be checked again. Your message was not sent and is still here.";
  if (code === 403) {
    if (
      context === "case-coordination" &&
      error instanceof CompassApiError &&
      readApiErrorCode(error.body) === "guidance_messages_case_coordination_ended"
    ) {
      return CASE_COORDINATION_ENDED_COPY;
    }
    return "Your account can no longer send this message. It was not sent.";
  }
  if (code === 422) {
    return "Your message was not sent. It must contain text and be no longer than 4,000 characters.";
  }
  if (code === 429) return "Too many messages were sent in a short time. Wait a moment, then send it again.";
  if (code === 404) {
    if (context === "case-coordination") return CASE_COORDINATION_UNAVAILABLE_COPY;
    if (context === "student-counseling") {
      return "This Counseling relationship can no longer receive messages. Your message was not sent; choose another recipient.";
    }
    if (context === "staff-office") {
      return "This Student is no longer in your workload. Your message was not sent; search again and choose another Student.";
    }
    if (context === "counselor-direct") {
      return "This Counselor is no longer available to receive messages. Your message was not sent; choose another Counselor.";
    }
    if (context === "referral-coordination") {
      return "This Referral is no longer available to your account. Your message was not sent.";
    }
    return "This conversation is no longer available. Your message was not sent.";
  }
  if (code === 409) {
    if (
      context === "referral-coordination" &&
      error instanceof CompassApiError &&
      readApiErrorCode(error.body) === "guidance_messages_referral_voided"
    ) {
      return "This Referral was voided, so the conversation is read-only. Your message was not sent.";
    }
    if (context === "faculty-inquiry") {
      return "Couldn't start your inquiry because the Guidance Office cannot receive it right now. Your message was not sent; try again later.";
    }
    if (context === "student-office") {
      return "The Guidance Office can't receive messages from your account right now; your message was not sent. Try again later or visit the Guidance Office.";
    }
    if (context === "staff-office") {
      return "This Student's College has no Guidance Office staff available to receive this conversation. Your message was not sent.";
    }
    if (context === "counselor-direct") {
      return "Couldn't start a conversation with this Counselor right now. Your message was not sent; try again later.";
    }
    return "This conversation is closed, so your message was not sent. Your text is still here.";
  }
  return "Your message was not sent.";
}

export function describeStatusChangeError(error: unknown, action: "resolve" | "reopen"): string {
  if (
    error instanceof CompassApiError &&
    readApiErrorCode(error.body) === "guidance_messages_referral_voided"
  ) {
    return "This Referral was voided, so this conversation cannot be closed or reopened.";
  }
  const code = status(error);
  if (action === "reopen" && code === 409) {
    return "This conversation cannot be reopened because the Student already has an open Guidance Office conversation.";
  }
  if (code === 404 || code === 403) return "This conversation is no longer available to your account.";
  if (code === 401) return "Your session needs to be checked again before this conversation can change.";
  return action === "resolve"
    ? "Couldn't close the conversation. Try again."
    : "Couldn't reopen the conversation. Try again.";
}

export function describeOlderError(error: unknown): string {
  return status(error) === 503
    ? "Couldn't load older messages right now. Try again."
    : "Couldn't load older messages. Try again.";
}

export function describeAssignError(error: unknown): string {
  if (error instanceof AccountChangedError) return "The signed-in account changed, so this conversation was not assigned here.";
  const code = status(error);
  if (code === 422) {
    return "The person you chose can no longer be assigned this conversation. The list was refreshed; choose someone else.";
  }
  if (code === 404 || code === 403) return "This conversation is no longer available to your account.";
  if (code === 401) return "Your session needs to be checked again before this conversation can be assigned.";
  return "Couldn't assign the conversation. Try again.";
}
