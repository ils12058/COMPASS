import { useInfiniteQuery } from "@tanstack/react-query";

import { MESSAGE_BODY_LIMIT, messageLength } from "@/features/guidance-messages/guidance-message-send";
import {
  getGuidanceMessagesListTemplatesQueryKey,
  guidanceMessagesListTemplates,
} from "@/lib/api/generated/guidance-messages/guidance-messages";

// Message templates (ADR-104) are shared generic wording that staff insert into a draft and edit
// before sending. A template only prepares text: inserting one sends nothing and generates no
// client_message_id, and the Message that is finally sent is an ordinary Message that carries no
// trace of the template. Template text lives only in the QueryClient, never in storage or URLs.

export const TEMPLATE_TOO_LONG = `This template would make the message longer than ${MESSAGE_BODY_LIMIT.toLocaleString("en-PH")} characters.`;

/** Why a template was not inserted; the draft is then unchanged. */
export type TemplateInsertResult = "inserted" | "too_long" | "unavailable";

/**
 * The draft after inserting a template: the template alone in a blank draft, otherwise after the
 * existing text and one blank line. A nonblank draft is never replaced.
 */
export function insertTemplateText(draft: string, body: string): string {
  return draft.trim() === "" ? body : `${draft}\n\n${body}`;
}

export function templateInsertProblem(draft: string, body: string): "too_long" | null {
  return messageLength(insertTemplateText(draft, body)) > MESSAGE_BODY_LIMIT ? "too_long" : null;
}

/** One line for a list, with line breaks shown as spaces. */
export function templatePreview(body: string): string {
  return body.replace(/\s+/g, " ").trim();
}

/** Every template query, whatever its status, search or page. */
export function templatesQueryFamily() {
  return getGuidanceMessagesListTemplatesQueryKey();
}

export const PICKER_PAGE_SIZE = 20;

/** Active templates for the composer's picker, loaded only while it is open; more on request. */
export function useActiveTemplates(search: string, enabled: boolean) {
  const params = { status: "ACTIVE" as const, ...(search ? { search } : {}), page_size: PICKER_PAGE_SIZE };
  return useInfiniteQuery({
    queryKey: [...getGuidanceMessagesListTemplatesQueryKey(params), "picker"] as const,
    queryFn: ({ pageParam, signal }) => guidanceMessagesListTemplates({ ...params, page: pageParam }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.data.has_next ? last.data.page + 1 : undefined),
    enabled,
    retry: false,
  });
}
