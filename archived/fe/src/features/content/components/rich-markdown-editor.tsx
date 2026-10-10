"use client";

import dynamic from "next/dynamic";

const RichMarkdownEditorClient = dynamic(
  () =>
    import("@/features/content/components/rich-markdown-editor-client").then(
      (module) => module.RichMarkdownEditorClient,
    ),
  {
    ssr: false,
    loading: () => (
      <div
        role="status"
        className="min-h-56 rounded-xl border bg-card p-5 text-sm text-muted-foreground"
      >
        Loading editor…
      </div>
    ),
  },
);

export function RichMarkdownEditor({
  initialValue,
  onChange,
  disabled = false,
  ariaLabel,
}: {
  initialValue: string;
  onChange: (markdown: string) => void;
  disabled?: boolean;
  ariaLabel: string;
}) {
  return (
    <RichMarkdownEditorClient
      initialValue={initialValue}
      onChange={onChange}
      disabled={disabled}
      ariaLabel={ariaLabel}
    />
  );
}
