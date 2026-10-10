"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { pageBackLinkClass, PageHeader } from "@/components/ui/page-header";
import { Panel, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { workspaceTabClass } from "@/components/ui/workspace-tabs";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { TemplateEditorDialog } from "@/features/guidance-messages/guidance-message-template-editor";
import { templatePreview, templatesQueryFamily } from "@/features/guidance-messages/guidance-message-templates";
import { guidanceDateTime } from "@/features/guidance-messages/guidance-message-time";
import { getGuidanceMessagesAccess } from "@/features/guidance-messages/guidance-messages-access";
import { errorStatus } from "@/features/guidance-messages/guidance-messages-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  guidanceMessagesArchiveTemplate,
  guidanceMessagesRestoreTemplate,
  useGuidanceMessagesListTemplates,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceTemplateResponse, TemplateStatus } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

const PAGE_SIZE = 20;
const HEADING_ID = "message-templates-heading";

// Shared Message templates (ADR-104): generic wording that Guidance staff insert into a draft and
// edit before sending. This page manages them; it is not a content system. There is no delete:
// archiving takes a template out of the composer, restoring brings it back, and neither touches
// any Message already sent.

export function GuidanceMessageTemplatesPage() {
  const { user } = usePortalSession();
  const access = getGuidanceMessagesAccess(user);
  if (!access.canManageTemplates) {
    return (
      <WorkspaceUnavailable title="Message templates unavailable">
        Your account cannot manage Message templates.
      </WorkspaceUnavailable>
    );
  }
  // Keyed by account: an open editor and its unsaved text never carry over to another account.
  return <TemplatesWorkspace key={user.id} />;
}

function TemplatesWorkspace() {
  const queryClient = useQueryClient();
  const status = useActionStatus();
  const searchId = useId();
  const [view, setView] = useState<TemplateStatus>("ACTIVE");
  const [search, setSearch] = useState("");
  const [applied, setApplied] = useState("");
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ open: boolean; template: GuidanceTemplateResponse | null }>({ open: false, template: null });
  const [archiving, setArchiving] = useState<GuidanceTemplateResponse | null>(null);
  const [rowError, setRowError] = useState<{ id: string; text: string } | null>(null);
  const templates = useGuidanceMessagesListTemplates(
    { status: view, ...(applied ? { search: applied } : {}), page, page_size: PAGE_SIZE },
    { query: { retry: false } },
  );
  const settle = () => void queryClient.invalidateQueries({ queryKey: templatesQueryFamily() });
  const archive = useMutation({
    mutationFn: (template: GuidanceTemplateResponse) => guidanceMessagesArchiveTemplate(template.id),
    onSettled: settle,
  });
  const restore = useMutation({
    mutationFn: (template: GuidanceTemplateResponse) => guidanceMessagesRestoreTemplate(template.id),
    onSettled: settle,
  });

  const data = templates.data?.data;
  const items = data?.items ?? [];

  function switchView(next: TemplateStatus) {
    setView(next);
    setPage(1);
    setRowError(null);
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApplied(search.trim());
    setPage(1);
  }

  const openCreate = () => setEditor({ open: true, template: null });

  return (
    <section aria-labelledby={HEADING_ID}>
      <PageHeader
        title="Message templates"
        headingId={HEADING_ID}
        back={
          <GuardedPortalLink href="/portal/messages" className={cn(pageBackLinkClass, "gap-1.5")}>
            <ArrowLeft size={16} aria-hidden="true" />
            Messages
          </GuardedPortalLink>
        }
        actions={
          <Button onClick={openCreate}>
            <Plus size={16} aria-hidden="true" />
            Create template
          </Button>
        }
      />
      <Panel as="div">
        <div role="group" aria-label="Template view" className="flex flex-wrap gap-x-6 border-b border-brand-line px-4 sm:px-5">
          <button type="button" aria-pressed={view === "ACTIVE"} onClick={() => switchView("ACTIVE")} className={workspaceTabClass(view === "ACTIVE")}>
            Active
          </button>
          <button type="button" aria-pressed={view === "ARCHIVED"} onClick={() => switchView("ARCHIVED")} className={workspaceTabClass(view === "ARCHIVED")}>
            Archived
          </button>
        </div>
        <form role="search" aria-label="Message templates" className="flex items-end gap-2 border-b border-border px-4 py-3 sm:px-5" onSubmit={submitSearch}>
          <div className="min-w-0 flex-1 sm:max-w-sm">
            <Label htmlFor={searchId} className="sr-only">
              Search template names
            </Label>
            <Input
              id={searchId}
              type="search"
              autoComplete="off"
              maxLength={120}
              placeholder="Search template names…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>
        <div aria-busy={templates.isFetching}>
          {templates.isPending ? (
            <RowsSkeleton label="Loading templates…" rows={3} />
          ) : templates.isError ? (
            <PanelMessage
              role="alert"
              tone="danger"
              action={
                errorStatus(templates.error) === 403 ? null : (
                  <Button variant="secondary" disabled={templates.isFetching} onClick={() => void templates.refetch()}>
                    {templates.isFetching ? "Retrying…" : "Retry"}
                  </Button>
                )
              }
            >
              {errorStatus(templates.error) === 403
                ? "Your account can no longer manage Message templates."
                : "Templates could not be loaded."}
            </PanelMessage>
          ) : items.length === 0 ? (
            <PanelMessage
              action={
                view === "ACTIVE" && !applied ? (
                  <Button onClick={openCreate}>
                    <Plus size={16} aria-hidden="true" />
                    Create template
                  </Button>
                ) : null
              }
            >
              {applied ? "No templates match this search." : view === "ACTIVE" ? "No message templates yet." : "No archived templates."}
            </PanelMessage>
          ) : (
            <ul className="divide-y divide-border">
              {items.map((template) => (
                <li key={template.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-start sm:justify-between sm:px-5">
                  <div className="min-w-0">
                    <h2 className="break-words text-sm font-semibold text-ink">{template.name}</h2>
                    <p className="mt-0.5 line-clamp-2 break-words text-sm text-muted">{templatePreview(template.body)}</p>
                    <p className="mt-1 text-xs text-muted">
                      {template.status === "ARCHIVED" && template.archived_at
                        ? `Archived ${guidanceDateTime(template.archived_at)}`
                        : `Updated ${guidanceDateTime(template.updated_at)}`}
                    </p>
                    {rowError?.id === template.id ? (
                      <p role="alert" className="mt-1 text-sm text-danger">
                        {rowError.text}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {template.status === "ACTIVE" ? (
                      <>
                        <Button
                          variant="secondary"
                          aria-label={`Edit ${template.name}`}
                          onClick={() => setEditor({ open: true, template })}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="secondary"
                          aria-label={`Archive ${template.name}`}
                          onClick={() => {
                            archive.reset();
                            setArchiving(template);
                          }}
                        >
                          Archive
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="secondary"
                        aria-label={`Restore ${template.name}`}
                        disabled={restore.isPending && restore.variables?.id === template.id}
                        onClick={() => {
                          setRowError(null);
                          restore.mutate(template, {
                            onSuccess: () => status.show(`${template.name} restored.`),
                            onError: (error) => setRowError({ id: template.id, text: describeStatusError(error, "restore") }),
                          });
                        }}
                      >
                        {restore.isPending && restore.variables?.id === template.id ? "Restoring…" : "Restore"}
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {!templates.isPending && !templates.isError ? (
            <CanonicalPagination
              className="px-4 sm:px-5"
              page={data?.page ?? page}
              hasNext={data?.has_next ?? false}
              label="Template pages"
              onPageChange={setPage}
            />
          ) : null}
        </div>
      </Panel>
      <TemplateEditorDialog
        open={editor.open}
        template={editor.template}
        onOpenChange={(open) => setEditor((current) => ({ ...current, open }))}
        onSaved={(saved, created) => {
          setEditor({ open: false, template: null });
          status.show(created ? `${saved.name} created.` : `${saved.name} saved.`);
        }}
      />
      <ConsequentialActionDialog
        open={archiving !== null}
        title="Archive this template?"
        confirmLabel="Archive template"
        pendingLabel="Archiving…"
        pending={archive.isPending}
        error={archive.isError ? describeStatusError(archive.error, "archive") : null}
        onOpenChange={(open) => {
          if (!open) setArchiving(null);
        }}
        onConfirm={() => {
          if (!archiving) return;
          const template = archiving;
          archive.mutate(template, {
            onSuccess: () => {
              setArchiving(null);
              status.show(`${template.name} archived.`);
            },
          });
        }}
      >
        <p>
          It will no longer be offered when writing a message. Messages already sent and drafts that
          already include it do not change. You can restore it from Archived.
        </p>
      </ConsequentialActionDialog>
      <ActionStatus status={status.status} onDismiss={status.dismiss} />
    </section>
  );
}

function describeStatusError(error: unknown, action: "archive" | "restore"): string {
  const code = errorStatus(error);
  if (code === 404) return "This template no longer exists.";
  if (code === 403) return "Your account can no longer manage Message templates.";
  if (code === 401) return "Your session needs to be checked again.";
  return action === "archive" ? "The template could not be archived. Try again." : "The template could not be restored. Try again.";
}
