"use client";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { PanelMessage } from "@/components/ui/panel";
import { cacheThread } from "@/features/guidance-messages/guidance-conversation-data";
import { ConversationFrame } from "@/features/guidance-messages/guidance-conversation";
import { GuidanceMessageComposer } from "@/features/guidance-messages/guidance-message-composer";
import type { SendIntent } from "@/features/guidance-messages/guidance-message-send";
import { messageTemplatesFor } from "@/features/guidance-messages/guidance-messages-access";
import { guidanceDateTime } from "@/features/guidance-messages/guidance-message-time";
import {
  guidanceConversationQueryKey,
  guidanceDirectoryQueryFamily,
  type ConversationHistory,
} from "@/features/guidance-messages/guidance-messages-cache";
import { describeSendError, type GuidanceSendContext } from "@/features/guidance-messages/guidance-messages-errors";
import { GUIDANCE_OFFICE_LABEL, personName } from "@/features/guidance-messages/guidance-messages-presentation";
import { CONVERSATION_HEADING_ID, errorStatus } from "@/features/guidance-messages/guidance-messages-shared";
import { useGuidanceWorkspace } from "@/features/guidance-messages/guidance-messages-workspace";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { EligibleStudentPicker, type EligibleStudentOption } from "@/features/portal/components/eligible-student-picker";
import {
  guidanceMessagesOpenCounselingThread,
  guidanceMessagesOpenMyOfficeThread,
  guidanceMessagesOpenStudentOfficeThread,
  useGuidanceMessagesEligibleStudents,
  useGuidanceMessagesRecipientOptions,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceOpenResponse, GuidanceRelationshipOption } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";

// A conversation starts with its first Message; there is no empty conversation. The recipient
// travels inside the send intent's target, so a retry always goes where the first attempt went.
const OFFICE_TARGET = "office";
const appointmentTarget = (appointmentId: string) => `appointment:${appointmentId}`;
const studentTarget = (studentId: string) => `student:${studentId}`;

function targetValue(target: string, prefix: string): string {
  if (!target.startsWith(prefix)) throw new Error("This message has no recipient.");
  return target.slice(prefix.length);
}

/** The opened (or already open) thread becomes the cached detail; its first Message seeds history. */
function useOpenedThread() {
  const queryClient = useQueryClient();
  return useCallback(
    (opened: GuidanceOpenResponse) => {
      void invalidateGuidanceWork(queryClient);
      cacheThread(queryClient, opened.thread);
      if (opened.message.sequence === 1) {
        queryClient.setQueryData<ConversationHistory>(guidanceConversationQueryKey(opened.thread.id), {
          messages: [opened.message],
          hasOlder: false,
        });
      }
      void queryClient.invalidateQueries({ queryKey: guidanceDirectoryQueryFamily() });
    },
    [queryClient],
  );
}

export function GuidanceNewMessage() {
  const workspace = useGuidanceWorkspace();
  const focusOnOpen = useRef(workspace.moves > 0);
  useEffect(() => {
    if (!focusOnOpen.current) return;
    focusOnOpen.current = false;
    if (!workspace.isSplit()) focusHeading(CONVERSATION_HEADING_ID);
  }, [workspace]);

  const { access } = workspace;
  if (access.isStudent ? !access.canManageSelf : !access.canManageStaff) {
    return (
      <ConversationFrame title="New message">
        <PanelMessage>Your account cannot start Guidance conversations.</PanelMessage>
      </ConversationFrame>
    );
  }
  return access.isStudent ? <StudentNewMessage /> : <StaffNewMessage />;
}

function useNavigateToThread() {
  const router = useRouter();
  return useCallback(
    (opened: { data: GuidanceOpenResponse }) => router.push(`/portal/messages/${opened.data.thread.id}`),
    [router],
  );
}

function StudentNewMessage() {
  const opened = useOpenedThread();
  const navigate = useNavigateToThread();
  const [page, setPage] = useState(1);
  const [recipient, setRecipient] = useState<string>(OFFICE_TARGET);
  const [relationship, setRelationship] = useState<GuidanceRelationshipOption | null>(null);
  const [locked, setLocked] = useState(false);
  const options = useGuidanceMessagesRecipientOptions({ page, page_size: 10 }, { query: { retry: false } });
  const open = useMutation({
    mutationFn: (intent: SendIntent) => {
      const payload = { client_message_id: intent.clientMessageId, body: intent.body };
      return intent.target === OFFICE_TARGET
        ? guidanceMessagesOpenMyOfficeThread(payload)
        : guidanceMessagesOpenCounselingThread(targetValue(intent.target, "appointment:"), payload);
    },
    onSuccess: (response) => opened(response.data),
    onError: (error) => {
      if (errorStatus(error) === 404) void options.refetch();
    },
  });

  const send = useCallback((intent: SendIntent) => open.mutateAsync(intent), [open]);
  const context: GuidanceSendContext = recipient === OFFICE_TARGET ? "student-office" : "student-counseling";
  const describe = useCallback((error: unknown) => describeSendError(error, context), [context]);
  const officeLabel = options.data?.data.office_label ?? GUIDANCE_OFFICE_LABEL;
  const relationships = options.data?.data.counseling_relationships ?? [];
  const recipientName = recipient === OFFICE_TARGET ? officeLabel : personName(relationship?.counselor, "your Counselor");

  return (
    <ConversationFrame title="New message">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <fieldset disabled={locked} className="min-w-0">
          <legend className="text-sm font-semibold text-ink">To</legend>
          <ul className="mt-2 divide-y divide-border rounded-sm border border-border">
            <li>
              <RecipientOption
                name="guidance-recipient"
                checked={recipient === OFFICE_TARGET}
                onSelect={() => setRecipient(OFFICE_TARGET)}
                title={officeLabel}
                detail="Guidance and Counseling Office"
              />
            </li>
          </ul>
          <h3 className="mt-5 text-sm font-semibold text-ink">My Counselor</h3>
          {options.isPending ? (
            <p role="status" className="mt-2 text-sm text-muted">Loading your Counseling relationships…</p>
          ) : options.isError ? (
            <div role="alert" className="mt-2">
              <p className="text-sm text-danger">Your Counseling relationships could not be loaded.</p>
              <Button className="mt-2" variant="secondary" onClick={() => void options.refetch()}>
                Retry
              </Button>
            </div>
          ) : relationships.length === 0 ? (
            <p className="mt-2 text-sm text-muted">
              {page > 1 ? "No more Counseling relationships." : "You can message a Counselor here after a Counseling appointment with them."}
            </p>
          ) : (
            <ul className="mt-2 divide-y divide-border rounded-sm border border-border">
              {relationships.map((option) => (
                <li key={option.appointment_id}>
                  <RecipientOption
                    name="guidance-recipient"
                    checked={recipient === appointmentTarget(option.appointment_id)}
                    onSelect={() => {
                      setRecipient(appointmentTarget(option.appointment_id));
                      setRelationship(option);
                    }}
                    title={personName(option.counselor, "Counselor")}
                    detail={`Counseling appointment · ${guidanceDateTime(option.starts_at)}`}
                  />
                </li>
              ))}
            </ul>
          )}
          {!options.isPending && !options.isError ? (
            <CanonicalPagination
              className="mt-2 border-t-0 py-2"
              page={options.data?.data.page ?? page}
              hasNext={options.data?.data.has_next ?? false}
              label="Counseling relationship pages"
              onPageChange={setPage}
            />
          ) : null}
        </fieldset>
        <p className="mt-4 text-sm text-muted">
          {recipient === OFFICE_TARGET
            ? "If you already have an open conversation with the Guidance Office, this message is added to it."
            : "If you already have a conversation for this appointment, this message is added to it."}
        </p>
      </div>
      <GuidanceMessageComposer
        target={recipient}
        label={`Message to ${recipientName}`}
        send={send}
        describeError={describe}
        onSent={navigate}
        onPendingChange={setLocked}
      />
    </ConversationFrame>
  );
}

function StaffNewMessage() {
  const { access } = useGuidanceWorkspace();
  const opened = useOpenedThread();
  const navigate = useNavigateToThread();
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [student, setStudent] = useState<EligibleStudentOption | null>(null);
  const [locked, setLocked] = useState(false);
  // Only Students in the reader's current workload: never the Accounts directory.
  const students = useGuidanceMessagesEligibleStudents(
    { ...(appliedSearch ? { search: appliedSearch } : {}), page, page_size: 10 },
    { query: { retry: false } },
  );
  const open = useMutation({
    mutationFn: (intent: SendIntent) =>
      guidanceMessagesOpenStudentOfficeThread(targetValue(intent.target, "student:"), {
        client_message_id: intent.clientMessageId,
        body: intent.body,
      }),
    onSuccess: (response) => opened(response.data),
    onError: (error) => {
      if (errorStatus(error) === 404) void students.refetch();
    },
  });
  const send = useCallback((intent: SendIntent) => open.mutateAsync(intent), [open]);
  const describe = useCallback((error: unknown) => describeSendError(error, "staff-office"), []);
  const pageData = students.data?.data;

  return (
    <ConversationFrame title="New message">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <fieldset disabled={locked} className="min-w-0">
          <EligibleStudentPicker
            label="Student"
            search={search}
            onSearchChange={setSearch}
            onSearch={() => {
              setAppliedSearch(search.trim());
              setPage(1);
            }}
            items={pageData?.items ?? []}
            selectedStudent={student}
            selectedId={student?.id ?? null}
            onSelect={setStudent}
            page={pageData?.page ?? page}
            hasNext={pageData?.has_next ?? false}
            isLoading={students.isPending}
            isError={students.isError}
            errorMessage="Students could not be loaded."
            onRetry={() => void students.refetch()}
            onPageChange={setPage}
          />
        </fieldset>
        {student ? (
          <p className="mt-4 text-sm text-muted">
            This message goes to the Guidance Office conversation for {student.display_name}. If one is
            already open, it is added there.
          </p>
        ) : null}
      </div>
      <GuidanceMessageComposer
        target={student ? studentTarget(student.id) : null}
        label={student ? `Message to ${student.display_name}` : "Message"}
        send={send}
        describeError={describe}
        onSent={navigate}
        onPendingChange={setLocked}
        unavailable={student ? null : "Choose a Student to write to."}
        templates={messageTemplatesFor(access)}
      />
    </ConversationFrame>
  );
}

function RecipientOption({
  name,
  checked,
  onSelect,
  title,
  detail,
}: {
  name: string;
  checked: boolean;
  onSelect: () => void;
  title: string;
  detail: string;
}) {
  return (
    <label className="flex min-h-11 cursor-pointer items-start gap-3 px-3 py-3 text-sm text-ink transition-colors hover:bg-surface-subtle has-[:checked]:bg-brand-wash has-[:disabled]:cursor-not-allowed">
      <input className="mt-1 h-4 w-4 shrink-0 accent-brand" type="radio" name={name} checked={checked} onChange={onSelect} />
      <span className="min-w-0">
        <span className="block break-words font-semibold">{title}</span>
        <span className="mt-0.5 block break-words text-xs text-muted">{detail}</span>
      </span>
    </label>
  );
}
