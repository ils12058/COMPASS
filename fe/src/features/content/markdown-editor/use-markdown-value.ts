"use client";

import { useRef, useState } from "react";

import type { MarkdownEditorHandle } from "@/features/content/markdown-editor/markdown-editor-types";

// Tracks a form's body Markdown. The saved string is kept as-is until the
// author edits, so saving never rewrites Markdown the author did not change,
// and editor normalization of the loaded content does not count as an edit.
export function useMarkdownValue(savedValue: string) {
  const handle = useRef<MarkdownEditorHandle | null>(null);
  const [initialValue] = useState(savedValue);
  const [value, setValue] = useState(savedValue);
  const [saved, setSaved] = useState(savedValue);
  const [normalizedSaved, setNormalizedSaved] = useState<string | null>(null);

  const isUnchanged = (markdown: string) => markdown === saved || markdown === normalizedSaved;

  // The editor's current Markdown, including edits made within the change
  // notification's debounce window.
  function readCurrent(): string {
    return handle.current?.getMarkdown() ?? value;
  }

  return {
    value,
    changed: !isUnchanged(value),
    readCurrent,
    // Null when the body matches the saved Markdown and should not be sent.
    readChanged(): string | null {
      const current = readCurrent();
      return isUnchanged(current) ? null : current;
    },
    // Call only when the body was sent. The editor keeps any typing done
    // while the save was in flight, so the current value is not replaced.
    markSaved(markdown: string) {
      setSaved(markdown);
      setNormalizedSaved(markdown);
    },
    editorProps: {
      initialValue,
      onChange: setValue,
      onReady: (next: MarkdownEditorHandle) => {
        handle.current = next;
        setNormalizedSaved(next.normalizedInitialValue);
      },
    },
  };
}
