"use client";

import { useId, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import {
  TEMPLATE_TOO_LONG,
  templatePreview,
  useActiveTemplates,
  type TemplateInsertResult,
} from "@/features/guidance-messages/guidance-message-templates";
import type { GuidanceTemplateResponse } from "@/lib/api/generated/model";

/**
 * Chooses an active Message template for the composer (ADR-104). Choosing one inserts its text into
 * the draft and returns focus there; nothing is sent. Search runs only when submitted.
 */
export function MessageTemplatePicker({
  open,
  onOpenChange,
  canManage,
  onChoose,
  onInserted,
  onDismissed,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Template managers get a way to the templates page when there is nothing to choose. */
  canManage: boolean;
  onChoose: (body: string) => TemplateInsertResult;
  /** Called after the picker closed with an inserted template, to put focus back in the draft. */
  onInserted: () => void;
  /** Called after the picker closed without one. Safari never focused the button that opened it. */
  onDismissed: () => void;
}) {
  const inserted = useRef(false);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
          closeLabel="Close templates"
          aria-describedby={undefined}
          className="flex max-h-[min(36rem,calc(100dvh-2rem))] flex-col overflow-hidden p-0"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (inserted.current) onInserted();
            else onDismissed();
            inserted.current = false;
          }}
        >
          <PickerBody
            canManage={canManage}
            onChoose={(template) => {
              const result = onChoose(template.body);
              if (result === "inserted") {
                inserted.current = true;
                onOpenChange(false);
              }
              return result;
            }}
          />
      </DialogContent>
    </Dialog>
  );
}

function PickerBody({
  canManage,
  onChoose,
}: {
  canManage: boolean;
  onChoose: (template: GuidanceTemplateResponse) => TemplateInsertResult;
}) {
  const searchId = useId();
  const [search, setSearch] = useState("");
  const [applied, setApplied] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const templates = useActiveTemplates(applied, true);
  const items = templates.data?.pages.flatMap((page) => page.data.items) ?? [];

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // The picker is portaled from inside the composer's form; its search never reaches that form.
    event.stopPropagation();
    setProblem(null);
    setApplied(search.trim());
  }

  return (
    <>
      <div className="border-b border-brand-line px-5 pt-5 pb-4">
        <DialogTitle className="text-lg">Templates</DialogTitle>
        <form role="search" aria-label="Templates" className="mt-3 flex items-end gap-2" onSubmit={submit}>
          <div className="min-w-0 flex-1">
            <Label htmlFor={searchId} className="sr-only">
              Search templates
            </Label>
            <Input
              id={searchId}
              type="search"
              autoComplete="off"
              maxLength={120}
              placeholder="Search templates…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4" aria-busy={templates.isFetching}>
        {problem ? (
          <p role="alert" className="mb-3 text-sm text-danger">
            {problem}
          </p>
        ) : null}
        {templates.isPending ? (
          <p role="status" className="text-sm text-muted">Loading templates…</p>
        ) : templates.isError && items.length === 0 ? (
          <div role="alert">
            <p className="text-sm text-danger">Templates could not be loaded.</p>
            <Button className="mt-3" variant="secondary" onClick={() => void templates.refetch()}>
              Retry
            </Button>
          </div>
        ) : items.length === 0 ? (
          <div className="text-sm text-muted">
            <p>{applied ? "No templates match this search." : "No message templates yet."}</p>
            {canManage && !applied ? (
              <GuardedPortalLink
                href="/portal/messages/templates"
                className="mt-2 inline-flex min-h-10 items-center font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Manage templates
              </GuardedPortalLink>
            ) : null}
          </div>
        ) : (
          <>
            <ul className="divide-y divide-border rounded-sm border border-border">
              {items.map((template) => (
                <li key={template.id}>
                  <TemplateOption
                    template={template}
                    onChoose={() => {
                      const result = onChoose(template);
                      setProblem(
                        result === "too_long"
                          ? TEMPLATE_TOO_LONG
                          : result === "unavailable"
                            ? "A template can be added once your message is no longer being sent."
                            : null,
                      );
                    }}
                  />
                </li>
              ))}
            </ul>
            {templates.hasNextPage ? (
              <Button
                className="mt-3"
                variant="secondary"
                disabled={templates.isFetchingNextPage}
                onClick={() => void templates.fetchNextPage()}
              >
                {templates.isFetchingNextPage ? "Loading…" : "Show more templates"}
              </Button>
            ) : null}
            {templates.isError ? (
              <p role="alert" className="mt-3 text-sm text-danger">More templates could not be loaded.</p>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}

function TemplateOption({ template, onChoose }: { template: GuidanceTemplateResponse; onChoose: () => void }) {
  const nameId = useId();
  const previewId = useId();
  return (
    <button
      type="button"
      aria-labelledby={nameId}
      aria-describedby={previewId}
      onClick={onChoose}
      className="block min-h-11 w-full px-3 py-2.5 text-left transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
    >
      <span id={nameId} className="block break-words text-sm font-semibold text-ink">
        {template.name}
      </span>
      <span id={previewId} className="mt-0.5 line-clamp-2 break-words text-xs text-muted">
        {templatePreview(template.body)}
      </span>
    </button>
  );
}
