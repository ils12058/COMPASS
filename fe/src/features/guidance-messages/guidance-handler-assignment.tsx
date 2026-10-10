"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cacheThread } from "@/features/guidance-messages/guidance-conversation-data";
import { guidanceDirectoryQueryFamily } from "@/features/guidance-messages/guidance-messages-cache";
import { describeAssignError } from "@/features/guidance-messages/guidance-messages-errors";
import { handlerRoleLabel, personName } from "@/features/guidance-messages/guidance-messages-presentation";
import { errorStatus } from "@/features/guidance-messages/guidance-messages-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  guidanceMessagesAssignHandler,
  useGuidanceMessagesListEligibleHandlers,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceHandlerOption, GuidanceThreadResponse } from "@/lib/api/generated/model";

const PAGE_SIZE = 10;

// Office handler assignment (ADR-104). Assignment records who follows up on an Office conversation;
// it never decides who can read it. Candidates come only from the thread's eligible-handler list,
// never from the Accounts directory, and the assignment itself is checked again when it is saved.

/** "Assigned to …" and, for staff who manage the conversation, the control to change it. */
export function ThreadAssignment({
  thread,
  currentUserId,
  canChange,
  onAssigned,
}: {
  thread: GuidanceThreadResponse;
  currentUserId: string;
  canChange: boolean;
  onAssigned?: (text: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const assignee = thread.assigned_to;
  const text = !assignee
    ? "Not assigned"
    : assignee.id === currentUserId
      ? "Assigned to you"
      : `Assigned to ${personName(assignee, "Guidance staff")}`;
  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-0.5 text-xs">
      <span className="min-w-0 break-words">{text}</span>
      {canChange ? (
        <>
          <Button
            ref={triggerRef}
            variant="quiet"
            className="min-h-10 px-2 text-xs"
            aria-haspopup="dialog"
            aria-label={assignee ? "Change assignment" : "Assign conversation"}
            onClick={() => setOpen(true)}
          >
            {assignee ? "Change" : "Assign"}
          </Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent
              closeLabel="Close assignment"
              aria-describedby={undefined}
              className="flex max-h-[min(40rem,calc(100dvh-2rem))] flex-col overflow-hidden p-0"
              // Back to Change, which Safari never focused when it was clicked.
              onCloseAutoFocus={(event) => {
                event.preventDefault();
                triggerRef.current?.focus();
              }}
            >
              <AssignmentBody
                thread={thread}
                currentUserId={currentUserId}
                onCancel={() => setOpen(false)}
                onAssigned={(name) => {
                  setOpen(false);
                  onAssigned?.(`Conversation assigned to ${name}.`);
                }}
              />
            </DialogContent>
          </Dialog>
        </>
      ) : null}
    </div>
  );
}

function AssignmentBody({
  thread,
  currentUserId,
  onCancel,
  onAssigned,
}: {
  thread: GuidanceThreadResponse;
  currentUserId: string;
  onCancel: () => void;
  onAssigned: (name: string) => void;
}) {
  const queryClient = useQueryClient();
  const searchId = useId();
  const noteId = useId();
  const [search, setSearch] = useState("");
  const [applied, setApplied] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<GuidanceHandlerOption | null>(null);
  const handlers = useGuidanceMessagesListEligibleHandlers(
    thread.id,
    { ...(applied ? { search: applied } : {}), page, page_size: PAGE_SIZE },
    { query: { retry: false } },
  );
  const assign = useMutation({
    mutationFn: (handler: GuidanceHandlerOption) => guidanceMessagesAssignHandler(thread.id, { handler_id: handler.id }),
    onSuccess: (response) => {
      cacheThread(queryClient, response.data);
      void queryClient.invalidateQueries({ queryKey: guidanceDirectoryQueryFamily() });
    },
  });
  const pageData = handlers.data?.data;
  const items = pageData?.items ?? [];
  const current = thread.assigned_to?.id ?? null;

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApplied(search.trim());
    setPage(1);
    setSelected(null);
  }

  function confirm() {
    if (!selected || selected.id === current) return;
    assign.mutate(selected, {
      onSuccess: () => onAssigned(selected.id === currentUserId ? "you" : personName(selected, "the selected staff member")),
      onError: (error) => {
        // The list was only advice: whoever was chosen may no longer be eligible. Show the current one.
        if (errorStatus(error) === 422) {
          setSelected(null);
          void handlers.refetch();
        }
      },
    });
  }

  const error = assign.isError ? describeAssignError(assign.error) : null;
  return (
    <>
      <div className="border-b border-brand-line px-5 pt-5 pb-4">
        <DialogTitle className="text-lg">Assign conversation</DialogTitle>
        <p id={noteId} className="mt-1 text-sm text-muted">
          Assignment shows who follows up. It does not change who can read this conversation.
        </p>
        <form role="search" aria-label="Eligible staff" className="mt-3 flex items-end gap-2" onSubmit={submitSearch}>
          <div className="min-w-0 flex-1">
            <Label htmlFor={searchId} className="sr-only">
              Search staff
            </Label>
            <Input
              id={searchId}
              type="search"
              autoComplete="off"
              maxLength={160}
              placeholder="Search staff…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4" aria-busy={handlers.isFetching}>
        {error ? (
          <p role="alert" className="mb-3 text-sm text-danger">
            {error}
          </p>
        ) : null}
        {handlers.isPending ? (
          <p role="status" className="text-sm text-muted">Loading staff…</p>
        ) : handlers.isError ? (
          <div role="alert">
            <p className="text-sm text-danger">
              {errorStatus(handlers.error) === 404 ? "This conversation is no longer available to your account." : "Staff could not be loaded."}
            </p>
            {errorStatus(handlers.error) !== 404 ? (
              <Button className="mt-3" variant="secondary" onClick={() => void handlers.refetch()}>
                Retry
              </Button>
            ) : null}
          </div>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted">{applied ? "No eligible staff match this search." : "No staff can be assigned this conversation right now."}</p>
        ) : (
          <fieldset disabled={assign.isPending} className="min-w-0" aria-describedby={noteId}>
            <legend className="sr-only">Eligible staff</legend>
            <ul className="divide-y divide-border rounded-sm border border-border">
              {items.map((handler) => (
                <li key={handler.id}>
                  <label className="flex min-h-11 cursor-pointer items-start gap-3 px-3 py-2.5 text-sm text-ink transition-colors hover:bg-surface-subtle has-[:checked]:bg-brand-wash has-[:disabled]:cursor-not-allowed">
                    <input
                      className="mt-1 h-4 w-4 shrink-0 accent-brand"
                      type="radio"
                      name="guidance-handler"
                      value={handler.id}
                      checked={selected?.id === handler.id}
                      onChange={() => setSelected(handler)}
                    />
                    <span className="min-w-0">
                      <span className="block break-words font-semibold">
                        {personName(handler, "Unnamed staff member")}
                        {handler.id === currentUserId ? " (you)" : ""}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {handlerRoleLabel(handler.role)}
                        {handler.id === current ? " · Currently assigned" : ""}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        )}
        {!handlers.isPending && !handlers.isError ? (
          <CanonicalPagination
            className="mt-2 border-t-0 pb-0"
            page={pageData?.page ?? page}
            hasNext={pageData?.has_next ?? false}
            label="Eligible staff pages"
            disabled={assign.isPending}
            onPageChange={(next) => {
              setPage(next);
              setSelected(null);
            }}
          />
        ) : null}
      </div>
      <div className="flex flex-col-reverse gap-2 border-t border-brand-line px-5 py-4 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onCancel} disabled={assign.isPending}>
          Cancel
        </Button>
        <Button onClick={confirm} disabled={!selected || selected.id === current || assign.isPending}>
          {assign.isPending ? "Assigning…" : "Assign"}
        </Button>
      </div>
    </>
  );
}
