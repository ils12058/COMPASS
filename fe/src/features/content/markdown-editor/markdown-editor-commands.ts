import type { Mark, MarkType, Node, NodeType, ResolvedPos } from "@milkdown/kit/prose/model";
import { redoDepth, undoDepth } from "@milkdown/kit/prose/history";
import type { EditorState, Transaction } from "@milkdown/kit/prose/state";

export type MarkdownSchemaTypes = {
  strong: MarkType;
  emphasis: MarkType;
  link: MarkType;
  paragraph: NodeType;
  heading: NodeType;
  blockquote: NodeType;
  bulletList: NodeType;
  orderedList: NodeType;
  listItem: NodeType;
};

export type MarkdownBlockStyle =
  | { kind: "paragraph" }
  | { kind: "heading"; level: number }
  | { kind: "other" };

export type MarkdownToolbarState = {
  block: MarkdownBlockStyle;
  bold: boolean;
  italic: boolean;
  link: boolean;
  bulletList: boolean;
  orderedList: boolean;
  blockquote: boolean;
  canUndo: boolean;
  canRedo: boolean;
};

export const emptyToolbarState: MarkdownToolbarState = {
  block: { kind: "paragraph" },
  bold: false,
  italic: false,
  link: false,
  bulletList: false,
  orderedList: false,
  blockquote: false,
  canUndo: false,
  canRedo: false,
};

type Ancestor = { node: Node; pos: number };

function nearestAncestor($pos: ResolvedPos, matches: (type: NodeType) => boolean): Ancestor | null {
  for (let depth = $pos.depth; depth > 0; depth -= 1) {
    const node = $pos.node(depth);
    if (matches(node.type)) return { node, pos: $pos.before(depth) };
  }
  return null;
}

function markActive(state: EditorState, type: MarkType): boolean {
  const { empty, from, to, $from } = state.selection;
  if (empty) return Boolean(type.isInSet(state.storedMarks ?? $from.marks()));
  return state.doc.rangeHasMark(from, to, type);
}

export function nearestList(state: EditorState, types: MarkdownSchemaTypes): Ancestor | null {
  return nearestAncestor(
    state.selection.$from,
    (type) => type === types.bulletList || type === types.orderedList,
  );
}

export function readToolbarState(state: EditorState, types: MarkdownSchemaTypes): MarkdownToolbarState {
  const parent = state.selection.$from.parent;
  const block: MarkdownBlockStyle =
    parent.type === types.paragraph
      ? { kind: "paragraph" }
      : parent.type === types.heading
        ? { kind: "heading", level: Number(parent.attrs.level) }
        : { kind: "other" };
  const list = nearestList(state, types);
  return {
    block,
    bold: markActive(state, types.strong),
    italic: markActive(state, types.emphasis),
    link: markActive(state, types.link),
    bulletList: list?.node.type === types.bulletList,
    orderedList: list?.node.type === types.orderedList,
    blockquote: nearestAncestor(state.selection.$from, (type) => type === types.blockquote) !== null,
    canUndo: undoDepth(state) > 0,
    canRedo: redoDepth(state) > 0,
  };
}

// Changes an existing list between bulleted and numbered in place. Items carry
// their own list type and label, which the preset's order sync reads, so they
// are updated together with the list node.
export function switchListType(
  state: EditorState,
  list: Ancestor,
  target: NodeType,
  types: MarkdownSchemaTypes,
): Transaction {
  const ordered = target === types.orderedList;
  const tr = state.tr.setNodeMarkup(
    list.pos,
    target,
    ordered ? { order: 1, spread: list.node.attrs.spread } : { spread: list.node.attrs.spread },
  );
  list.node.forEach((child, offset, index) => {
    if (child.type !== types.listItem) return;
    tr.setNodeMarkup(list.pos + 1 + offset, undefined, {
      ...child.attrs,
      listType: ordered ? "ordered" : "bullet",
      label: ordered ? `${index + 1}.` : "•",
    });
  });
  return tr;
}

export type LinkRange = { from: number; to: number; href: string };

// The contiguous run of text carrying the same link mark around the cursor, or
// the selected range when text is selected.
export function linkRangeAtSelection(state: EditorState, linkType: MarkType): LinkRange | null {
  const { empty, from, to, $from } = state.selection;
  if (!empty) {
    let href: string | null = null;
    state.doc.nodesBetween(from, to, (node) => {
      const mark = linkType.isInSet(node.marks);
      if (mark && href === null) href = String(mark.attrs.href);
    });
    return href === null ? null : { from, to, href };
  }

  const cursorMark = linkType.isInSet($from.marks());
  if (!cursorMark) return null;
  const start = $from.start();
  const runs: { from: number; to: number; mark: Mark }[] = [];
  $from.parent.forEach((child, offset) => {
    const mark = linkType.isInSet(child.marks);
    if (!mark) return;
    const childFrom = start + offset;
    const last = runs[runs.length - 1];
    if (last && last.to === childFrom && last.mark.eq(mark)) last.to = childFrom + child.nodeSize;
    else runs.push({ from: childFrom, to: childFrom + child.nodeSize, mark });
  });
  const run = runs.find((item) => item.mark.eq(cursorMark) && item.from <= from && from <= item.to);
  return run ? { from: run.from, to: run.to, href: String(run.mark.attrs.href) } : null;
}

export function applyLink(
  state: EditorState,
  linkType: MarkType,
  href: string,
  text: string,
): Transaction {
  const existing = linkRangeAtSelection(state, linkType);
  const mark = linkType.create({ href });
  if (existing) {
    return state.tr.removeMark(existing.from, existing.to, linkType).addMark(existing.from, existing.to, mark);
  }
  const { empty, from, to } = state.selection;
  if (!empty) return state.tr.removeMark(from, to, linkType).addMark(from, to, mark);
  const label = text.trim() || href;
  return state.tr.replaceSelectionWith(state.schema.text(label, [mark]), false);
}

export function removeLink(state: EditorState, linkType: MarkType): Transaction | null {
  const existing = linkRangeAtSelection(state, linkType);
  return existing ? state.tr.removeMark(existing.from, existing.to, linkType) : null;
}
