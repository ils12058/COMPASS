"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export type MarkdownLinkDialogState = {
  href: string;
  editing: boolean;
  needsText: boolean;
};

// Published pages render only web addresses and COMPASS paths as links, so the
// editor accepts the same forms.
function validLinkTarget(value: string): boolean {
  if (value.startsWith("/")) return !value.startsWith("//") && !value.includes("\\");
  try {
    const url = new URL(value);
    return (url.protocol === "https:" || url.protocol === "http:") && Boolean(url.hostname);
  } catch {
    return false;
  }
}

export function MarkdownLinkDialog({
  state,
  onApply,
  onRemove,
  onClose,
  onRestoreFocus,
}: {
  state: MarkdownLinkDialogState | null;
  onApply: (href: string, text: string) => void;
  onRemove: () => void;
  onClose: () => void;
  onRestoreFocus: () => void;
}) {
  return (
    <Dialog open={state !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      {state ? (
        <LinkDialogBody
          state={state}
          onApply={onApply}
          onRemove={onRemove}
          onClose={onClose}
          onRestoreFocus={onRestoreFocus}
        />
      ) : null}
    </Dialog>
  );
}

function LinkDialogBody({
  state,
  onApply,
  onRemove,
  onClose,
  onRestoreFocus,
}: {
  state: MarkdownLinkDialogState;
  onApply: (href: string, text: string) => void;
  onRemove: () => void;
  onClose: () => void;
  onRestoreFocus: () => void;
}) {
  const [href, setHref] = useState(state.href);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // The dialog renders in a portal inside the content form; keep this submit
    // from reaching that form.
    event.stopPropagation();
    const target = href.trim();
    if (!validLinkTarget(target)) {
      setError("Enter a web address that starts with https:// or http://, or a COMPASS page path that starts with /.");
      return;
    }
    onApply(target, text);
  }

  return (
    <DialogContent
      onCloseAutoFocus={(event) => {
        // Return to the writing position instead of the toolbar button.
        event.preventDefault();
        onRestoreFocus();
      }}
    >
      <DialogTitle>{state.editing ? "Edit link" : "Add link"}</DialogTitle>
      <DialogDescription>
        Readers open web addresses in a new tab. COMPASS paths open in the same tab.
      </DialogDescription>
      <form className="mt-5 space-y-4" onSubmit={submit} noValidate>
        {state.needsText ? (
          <div className="grid gap-2">
            <Label htmlFor="markdown-link-text">Link text</Label>
            <Input
              id="markdown-link-text"
              value={text}
              maxLength={200}
              onChange={(event) => setText(event.target.value)}
            />
            <p className="text-xs leading-5 text-muted">Leave blank to show the address as the link text.</p>
          </div>
        ) : null}
        <div className="grid gap-2">
          <Label htmlFor="markdown-link-href">Web address or COMPASS path</Label>
          <Input
            id="markdown-link-href"
            inputMode="url"
            autoComplete="url"
            value={href}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "markdown-link-error" : undefined}
            onChange={(event) => {
              setHref(event.target.value);
              setError(null);
            }}
            placeholder="https://"
          />
          {error ? (
            <p id="markdown-link-error" role="alert" className="text-sm leading-6 text-danger">
              {error}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap justify-end gap-2 pt-2">
          {state.editing ? (
            <Button variant="quiet" className="mr-auto" onClick={onRemove}>
              Remove link
            </Button>
          ) : null}
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit">Apply link</Button>
        </div>
      </form>
    </DialogContent>
  );
}
