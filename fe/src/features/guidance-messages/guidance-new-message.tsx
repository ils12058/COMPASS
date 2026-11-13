"use client";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { PanelMessage } from "@/components/ui/panel";
import { CounselorAboutButton } from "@/features/counselor-about/counselor-about-dialog";
import { cacheThread } from "@/features/guidance-messages/guidance-conversation-data";
import { GuidanceIdentityAvatar } from "@/features/guidance-messages/guidance-conversation-identity";
import { ConversationFrame } from "@/features/guidance-messages/guidance-conversation";
import { GuidanceCounselorPeerPicker } from "@/features/guidance-messages/guidance-counselor-peer-picker";
import { GuidanceMessageComposer } from "@/features/guidance-messages/guidance-message-composer";
import type { SendIntent } from "@/features/guidance-messages/guidance-message-send";
import { messageTemplatesFor } from "@/features/guidance-messages/guidance-messages-access";
import {
  guidanceConversationQueryKey,
  guidanceDirectoryQueryFamily,
  type ConversationHistory,
} from "@/features/guidance-messages/guidance-messages-cache";
import { describeSendError, type GuidanceSendContext } from "@/features/guidance-messages/guidance-messages-errors";
import {
  GUIDANCE_OFFICE_LABEL,
  appointmentSummaryLabel,
  personName,
} from "@/features/guidance-messages/guidance-messages-presentation";
import { CONVERSATION_HEADING_ID, errorStatus } from "@/features/guidance-messages/guidance-messages-shared";
import { useGuidanceWorkspace } from "@/features/guidance-messages/guidance-messages-workspace";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { EligibleStudentPicker, type EligibleStudentOption } from "@/features/portal/components/eligible-student-picker";
import {
  guidanceMessagesOpenCounselingThread,
  guidanceMessagesOpenCounselorDirectThread,
  guidanceMessagesOpenFacultyInquiry,
  guidanceMessagesOpenMyOfficeThread,
  guidanceMessagesOpenReferralThread,
  guidanceMessagesOpenStudentOfficeThread,
  useGuidanceMessagesEligibleStudents,
  useGuidanceMessagesGetReferralContext,
  useGuidanceMessagesListCounselorPeers,
  useGuidanceMessagesRecipientOptions,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type {
  GuidanceOpenResponse,
  GuidancePerson,
  GuidanceRelationshipOption,
} from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import { cn } from "@/lib/utils/cn";

// A conversation starts with its first Message; there is no empty conversation. The recipient
// travels inside the send intent's target, so a retry always goes where the first attempt went.
const OFFICE_TARGET = "office";
const appointmentTarget = (appointmentId: string) => `appointment:${appointmentId}`;
const studentTarget = (studentId: string) => `student:${studentId}`;
const counselorTarget = (peerId: string) => `counselor:${peerId}`;

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
  const params = useSearchParams();
  const referralId = params.get("referral");
  const focusOnOpen = useRef(workspace.moves > 0);
  useEffect(() => {
    if (!focusOnOpen.current) return;
    focusOnOpen.current = false;
    if (!workspace.isSplit()) focusHeading(CONVERSATION_HEADING_ID);
  }, [workspace]);

  if (referralId) return <ReferralNewMessage referralId={referralId} />;

  const { access } = workspace;
  const canStart = access.isStudent
    ? access.canManageSelf
    : access.isFaculty
      ? access.canManageInquirySelf
      : access.canManageStaff || access.canManageDirect;
  if (!canStart) {
    return (
      <ConversationFrame title="New message">
        <PanelMessage>Your account cannot start Guidance conversations.</PanelMessage>
      </ConversationFrame>
    );
  }
  if (access.isStudent) return <StudentNewMessage />;
  return access.isFaculty ? <FacultyNewMessage /> : <StaffNewMessage />;
}

/**
 * A referral conversation starts from the Referral page, never from the generic chooser. Only the
 * Referral id travels here; the message body is typed in this composer and nowhere else.
 */
function ReferralNewMessage({ referralId }: { referralId: string }) {
  const router = useRouter();
  const { access } = useGuidanceWorkspace();
  const opened = useOpenedThread();
  const navigate = useNavigateToThread();
  const [locked, setLocked] = useState(false);
  const context = useGuidanceMessagesGetReferralContext(referralId, { query: { retry: false } });
  const thread = context.data?.data.thread ?? null;
  const canStart = context.data?.data.can_start ?? false;

  useEffect(() => {
    if (thread) router.replace(`/portal/messages/${thread.id}`);
  }, [router, thread]);

  const open = useMutation({
    mutationFn: (intent: SendIntent) =>
      guidanceMessagesOpenReferralThread(referralId, {
        client_message_id: intent.clientMessageId,
        body: intent.body,
      }),
    onSuccess: (response) => opened(response.data),
  });
  const send = useCallback((intent: SendIntent) => open.mutateAsync(intent), [open]);
  const describe = useCallback(
    (error: unknown) => describeSendError(error, "referral-coordination"),
    [],
  );

  if (context.isPending) {
    return (
      <ConversationFrame title="Message the Guidance Office">
        <PanelMessage role="status">Checking this Referral…</PanelMessage>
      </ConversationFrame>
    );
  }
  if (context.isError) {
    const notFound = errorStatus(context.error) === 404;
    return (
      <ConversationFrame title="Message the Guidance Office">
        <PanelMessage
          role="alert"
          action={
            notFound ? undefined : (
              <Button variant="secondary" onClick={() => void context.refetch()}>
                Retry
              </Button>
            )
          }
        >
          {notFound ? "This Referral is no longer available." : "Couldn't load this Referral. Try again."}
        </PanelMessage>
      </ConversationFrame>
    );
  }
  if (thread) {
    return (
      <ConversationFrame title="Message the Guidance Office">
        <PanelMessage role="status">Opening the conversation…</PanelMessage>
      </ConversationFrame>
    );
  }
  if (!access.canManageReferralSelf) {
    return (
      <ConversationFrame title="Message the Guidance Office">
        <PanelMessage>Your account cannot message about this Referral.</PanelMessage>
      </ConversationFrame>
    );
  }
  if (!canStart) {
    return (
      <ConversationFrame title="Message the Guidance Office">
        <PanelMessage>This Referral cannot receive messages right now.</PanelMessage>
      </ConversationFrame>
    );
  }

  return (
    <ConversationFrame title="Message the Guidance Office">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <fieldset disabled={locked} className="min-w-0">
          <legend className="text-sm font-semibold text-ink">To</legend>
          <ul className="mt-2 divide-y divide-border rounded-sm border border-border">
            <li>
              <RecipientOption
                name="guidance-recipient"
                checked
                onSelect={() => undefined}
                title={GUIDANCE_OFFICE_LABEL}
                office
              />
            </li>
          </ul>
        </fieldset>
        <p className="mt-4 text-sm text-muted">
          This message is about the Referral you submitted. It goes to the Guidance Office and does not change the Referral record.
        </p>
      </div>
      <GuidanceMessageComposer
        target={`referral:${referralId}`}
        label={`Message to ${GUIDANCE_OFFICE_LABEL}`}
        send={send}
        describeError={describe}
        onSent={navigate}
        onPendingChange={setLocked}
      />
    </ConversationFrame>
  );
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
                office
              />
            </li>
          </ul>
          <h3 className="mt-5 text-sm font-semibold text-ink">My Counselor</h3>
          {options.isPending ? (
            <p role="status" className="mt-2 text-sm text-muted">Loading your Counseling relationships…</p>
          ) : options.isError ? (
            <div role="alert" className="mt-2">
              <p className="text-sm text-danger">Couldn&apos;t load your Counseling relationships. Try again.</p>
              <Button className="mt-2" variant="secondary" onClick={() => void options.refetch()}>
                Retry
              </Button>
            </div>
          ) : relationships.length === 0 ? (
            <p className="mt-2 text-sm text-muted">
              {page > 1 ? "No more Counseling relationships." : "You can message a Counselor here after a Counseling Appointment with them."}
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
                    detail={`${option.reference_code} · ${appointmentSummaryLabel(option)}`}
                    photoUrl={option.counselor.profile_photo_url}
                    photoUpdatedAt={option.counselor.profile_photo_updated_at}
                    aside={
                      <CounselorAboutButton
                        counselorId={option.counselor.id}
                        counselorName={personName(option.counselor, "Counselor")}
                      />
                    }
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
            : "If you already have a conversation for this Appointment, this message is added to it."}
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

function FacultyNewMessage() {
  const opened = useOpenedThread();
  const navigate = useNavigateToThread();
  const [locked, setLocked] = useState(false);
  // The Guidance Office is the only recipient, so no recipient search runs here.
  const open = useMutation({
    mutationFn: (intent: SendIntent) =>
      guidanceMessagesOpenFacultyInquiry({ client_message_id: intent.clientMessageId, body: intent.body }),
    onSuccess: (response) => opened(response.data),
  });
  const send = useCallback((intent: SendIntent) => open.mutateAsync(intent), [open]);
  const describe = useCallback((error: unknown) => describeSendError(error, "faculty-inquiry"), []);

  return (
    <ConversationFrame title="New message">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <fieldset disabled={locked} className="min-w-0">
          <legend className="text-sm font-semibold text-ink">To</legend>
          <ul className="mt-2 divide-y divide-border rounded-sm border border-border">
            <li>
              <RecipientOption
                name="guidance-recipient"
                checked
                onSelect={() => undefined}
                title={GUIDANCE_OFFICE_LABEL}
                office
              />
            </li>
          </ul>
        </fieldset>
        <p className="mt-4 text-sm text-muted">
          Your inquiry goes to the Guidance Office, which reads it and replies. Keep five or fewer
          inquiries open at a time.
        </p>
      </div>
      <GuidanceMessageComposer
        target={OFFICE_TARGET}
        label={`Message to ${GUIDANCE_OFFICE_LABEL}`}
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
  const [recipientType, setRecipientType] = useState<"student" | "counselor">(() =>
    access.canManageStaff ? "student" : "counselor",
  );
  const [studentSearch, setStudentSearch] = useState("");
  const [studentApplied, setStudentApplied] = useState("");
  const [studentPage, setStudentPage] = useState(1);
  const [student, setStudent] = useState<EligibleStudentOption | null>(null);
  const [peerSearch, setPeerSearch] = useState("");
  const [peerApplied, setPeerApplied] = useState("");
  const [peerPage, setPeerPage] = useState(1);
  const [peer, setPeer] = useState<GuidancePerson | null>(null);
  const [locked, setLocked] = useState(false);
  // Only Students in the reader's current workload: never the Accounts directory.
  const students = useGuidanceMessagesEligibleStudents(
    { ...(studentApplied ? { search: studentApplied } : {}), page: studentPage, page_size: 10 },
    { query: { retry: false, enabled: recipientType === "student" && access.canManageStaff } },
  );
  // Only active Counselors who may themselves start direct conversations.
  const peers = useGuidanceMessagesListCounselorPeers(
    { ...(peerApplied ? { search: peerApplied } : {}), page: peerPage, page_size: 10 },
    { query: { retry: false, enabled: recipientType === "counselor" && access.canManageDirect } },
  );
  const open = useMutation({
    mutationFn: (intent: SendIntent) => {
      const payload = { client_message_id: intent.clientMessageId, body: intent.body };
      const target = intent.target;
      if (target.startsWith("student:")) {
        return guidanceMessagesOpenStudentOfficeThread(targetValue(target, "student:"), payload);
      }
      return guidanceMessagesOpenCounselorDirectThread(targetValue(target, "counselor:"), payload);
    },
    onSuccess: (response) => opened(response.data),
    onError: (error) => {
      if (errorStatus(error) === 404) {
        if (recipientType === "student") void students.refetch();
        else void peers.refetch();
      }
    },
  });
  const send = useCallback((intent: SendIntent) => open.mutateAsync(intent), [open]);
  const describe = useCallback(
    (error: unknown) =>
      describeSendError(error, recipientType === "student" ? "staff-office" : "counselor-direct"),
    [recipientType],
  );
  const pageData = students.data?.data;
  const peerPageData = peers.data?.data;
  const target =
    recipientType === "student"
      ? student
        ? studentTarget(student.id)
        : null
      : peer
        ? counselorTarget(peer.id)
        : null;
  const recipientName =
    recipientType === "student" ? student?.display_name : peer?.display_name;

  return (
    <ConversationFrame title="New message">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <fieldset disabled={locked} className="min-w-0">
          {access.canManageStaff && access.canManageDirect ? (
            <>
              <legend className="text-sm font-semibold text-ink">To</legend>
              <ul className="mt-2 divide-y divide-border rounded-sm border border-border">
                <li>
                  <RecipientOption
                    name="guidance-recipient-type"
                    checked={recipientType === "student"}
                    onSelect={() => setRecipientType("student")}
                    title="Student"
                    showAvatar={false}
                    detail="The Student's Guidance Office conversation"
                  />
                </li>
                <li>
                  <RecipientOption
                    name="guidance-recipient-type"
                    checked={recipientType === "counselor"}
                    onSelect={() => setRecipientType("counselor")}
                    title="Counselor"
                    showAvatar={false}
                    detail="A direct conversation between Counselors"
                  />
                </li>
              </ul>
            </>
          ) : null}
          {recipientType === "student" && access.canManageStaff ? (
            <div className={cn(
              "[overflow-wrap:anywhere] [&_label:has(:focus)]:ring-2 [&_label:has(:focus)]:ring-inset [&_label:has(:focus)]:ring-focus",
              access.canManageStaff && access.canManageDirect && "mt-5",
            )}>
              <EligibleStudentPicker
                label="Student"
                search={studentSearch}
                onSearchChange={setStudentSearch}
                onSearch={() => {
                  setStudentApplied(studentSearch.trim());
                  setStudentPage(1);
                }}
                items={pageData?.items ?? []}
                selectedStudent={student}
                selectedId={student?.id ?? null}
                onSelect={setStudent}
                page={pageData?.page ?? studentPage}
                hasNext={pageData?.has_next ?? false}
                isLoading={students.isPending}
                isError={students.isError}
                errorMessage="Couldn't load Students. Try again."
                onRetry={() => void students.refetch()}
                onPageChange={setStudentPage}
              />
            </div>
          ) : null}
          {recipientType === "counselor" && access.canManageDirect ? (
            <div className={access.canManageStaff && access.canManageDirect ? "mt-5" : undefined}>
              <GuidanceCounselorPeerPicker
                label="Counselor"
                search={peerSearch}
                onSearchChange={setPeerSearch}
                onSearch={() => {
                  setPeerApplied(peerSearch.trim());
                  setPeerPage(1);
                }}
                items={peerPageData?.items ?? []}
                selectedPeer={peer}
                selectedId={peer?.id ?? null}
                onSelect={setPeer}
                page={peerPageData?.page ?? peerPage}
                hasNext={peerPageData?.has_next ?? false}
                isLoading={peers.isPending}
                isError={peers.isError}
                errorMessage="Couldn't load Counselors. Try again."
                onRetry={() => void peers.refetch()}
                onPageChange={setPeerPage}
              />
            </div>
          ) : null}
        </fieldset>
        {recipientType === "student" && student ? (
          <p className="mt-4 text-sm text-muted">
            This message goes to the Guidance Office conversation for {student.display_name}. If one is
            already open, it is added there.
          </p>
        ) : null}
        {recipientType === "counselor" && peer ? (
          <p className="mt-4 text-sm text-muted">
            This message goes to your conversation with {peer.display_name}. If you already have one,
            it is added there.
          </p>
        ) : null}
      </div>
      <GuidanceMessageComposer
        target={target}
        label={recipientName ? `Message to ${recipientName}` : "Message"}
        send={send}
        describeError={describe}
        onSent={navigate}
        onPendingChange={setLocked}
        unavailable={
          target
            ? null
            : recipientType === "student"
              ? "Choose a Student to write to."
              : "Choose a Counselor to write to."
        }
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
  office = false,
  showAvatar = true,
  photoUrl,
  photoUpdatedAt,
  aside,
}: {
  name: string;
  checked: boolean;
  onSelect: () => void;
  title: string;
  detail?: string;
  office?: boolean;
  showAvatar?: boolean;
  photoUrl?: string | null;
  photoUpdatedAt?: string | null;
  /** Shown beside the choice, outside its label, so it never selects the recipient. */
  aside?: ReactNode;
}) {
  const label = (
    <label data-guide-target="message-recipient" className="flex min-h-11 min-w-0 flex-1 cursor-pointer items-start gap-3 px-3 py-3 text-sm text-ink transition-colors hover:bg-surface-subtle has-[:checked]:bg-brand-wash has-[:disabled]:cursor-not-allowed has-[:focus]:ring-2 has-[:focus]:ring-inset has-[:focus]:ring-focus">
      <input className="mt-1 size-4 shrink-0 accent-brand" type="radio" name={name} checked={checked} onChange={onSelect} />
      {showAvatar ? <GuidanceIdentityAvatar name={title} office={office} photoUrl={photoUrl} photoUpdatedAt={photoUpdatedAt} /> : null}
      <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">
        <span className="block font-semibold">{title}</span>
        {detail ? <span className="mt-0.5 block text-sm text-muted">{detail}</span> : null}
      </span>
    </label>
  );
  if (!aside) return label;
  return (
    <div className="flex items-center gap-1 pr-2 has-[input:checked]:bg-brand-wash">
      {label}
      {aside}
    </div>
  );
}
