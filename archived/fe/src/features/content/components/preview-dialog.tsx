"use client";

import { Eye, X } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { MarkdownContent } from "@/features/public/components/markdown-content";

export function PreviewDialog({
  title,
  markdown,
}: {
  title: string;
  markdown: string;
}) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  function open() {
    returnFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.showModal();
    window.requestAnimationFrame(() => headingRef.current?.focus());
  }

  function close() {
    dialogRef.current?.close();
  }

  return (
    <>
      <Button variant="outline" onClick={open}>
        <Eye aria-hidden="true" className="size-4" />
        Preview
      </Button>
      <dialog
        ref={dialogRef}
        aria-labelledby="published-preview-title"
        className="m-auto max-h-[88vh] w-[min(94vw,54rem)] rounded-2xl border bg-card p-0 text-foreground shadow-md backdrop:bg-black/35"
        onClick={(event) => {
          if (event.target === dialogRef.current) {
            close();
          }
        }}
        onClose={() => returnFocusRef.current?.focus()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b bg-card p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--compass-support-strong)]">
              Preview as published
            </p>
            <h2
              ref={headingRef}
              id="published-preview-title"
              tabIndex={-1}
              className="mt-1 font-heading text-2xl font-bold"
            >
              {title.trim() || "Untitled"}
            </h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close preview" onClick={close}>
            <X aria-hidden="true" className="size-5" />
          </Button>
        </div>
        <div className="max-h-[calc(88vh-6rem)] overflow-y-auto p-6 sm:p-8">
          {markdown.trim() ? (
            <MarkdownContent source={markdown} />
          ) : (
            <p className="text-sm text-muted-foreground">There is no content to preview yet.</p>
          )}
        </div>
      </dialog>
    </>
  );
}
