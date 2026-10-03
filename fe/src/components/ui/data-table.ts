// Class names for dense record tables. A table sits flush inside a Panel, so the panel draws the
// frame; the head carries the maroon wash and the rows are separated by ordinary lines. With
// border-separate, row lines live on the cells, and a sticky identity column keeps the row's
// background on hover.
export const dataTable = {
  // Wide tables scroll sideways on narrow screens instead of turning into card stacks.
  scroll: "overflow-x-auto",
  table: "w-full border-separate border-spacing-0 text-left text-sm",
  head: "bg-brand-wash text-xs uppercase tracking-wide text-brand-strong",
  headerCell: "border-b border-brand-line px-4 py-2.5 align-bottom font-semibold",
  stickyHeaderCell: "sticky left-0 z-20 bg-brand-wash",
  body: "[&>tr:last-child>*]:border-b-0",
  row: "group transition-colors hover:bg-surface-subtle",
  cell: "border-b border-border px-4 py-3 align-top",
  stickyCell: "sticky left-0 z-10 bg-surface-raised transition-colors group-hover:bg-surface-subtle",
} as const;
