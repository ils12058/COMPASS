"use client";

import dynamic from "next/dynamic";
import { Component, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import type { MarkdownEditorProps } from "@/features/content/markdown-editor/markdown-editor-types";

function MarkdownEditorSkeleton() {
  return (
    <div aria-busy="true" className="rounded-md border border-border bg-surface-raised">
      <div className="flex gap-2 border-b border-border px-2 py-2">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-8 w-24" />
      </div>
      <div className="space-y-3 p-4">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </div>
      <p className="sr-only">Loading the editor…</p>
    </div>
  );
}

// Milkdown needs browser DOM APIs, so it loads only on the client and in its
// own chunk; forms that host it stay ordinary client components.
const MilkdownMarkdownEditor = dynamic(
  () =>
    import("@/features/content/markdown-editor/milkdown-markdown-editor").then(
      (module) => module.MilkdownMarkdownEditor,
    ),
  { ssr: false, loading: MarkdownEditorSkeleton },
);

class MarkdownEditorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div role="alert" className="rounded-md border border-danger/40 px-4 py-5 text-sm leading-6">
          <p className="font-semibold text-danger">The editor could not be loaded.</p>
          <p className="mt-1 text-muted">
            Reload the page to edit the body. Reloading discards changes that have not been saved.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export function MarkdownEditor(props: MarkdownEditorProps) {
  return (
    <MarkdownEditorBoundary>
      <MilkdownMarkdownEditor {...props} />
    </MarkdownEditorBoundary>
  );
}
