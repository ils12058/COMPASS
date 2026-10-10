// The portal shell gives every page the whole workspace, so collections (lists, tables, queues, and
// directories) can use it. A page that is not a collection — a record, a form, an editor, or a page
// of running text — keeps a bounded sheet so its fields and text stay readable. Put it on the page's
// outermost element. Pages that share workspace tabs share one width, so the tabs do not jump.
export const pageSheetWidth = "max-w-6xl";
