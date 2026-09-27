export type MarkdownEditorHandle = {
  // The loaded Markdown as the editor serializes it. Comparing against this
  // keeps editor normalization from counting as a change.
  normalizedInitialValue: string;
  // The editor's current Markdown, read directly rather than waiting for the
  // debounced change notification. Null after the editor is destroyed.
  getMarkdown: () => string | null;
};

export type MarkdownEditorProps = {
  id: string;
  labelId: string;
  describedBy?: string;
  invalid?: boolean;
  initialValue: string;
  onChange: (markdown: string) => void;
  onReady?: (handle: MarkdownEditorHandle) => void;
};
