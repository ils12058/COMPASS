"use client";

import "@milkdown/kit/prose/view/style/prosemirror.css";

import {
  Editor,
  commandsCtx,
  defaultValueCtx,
  editorViewCtx,
  editorViewOptionsCtx,
  rootCtx,
} from "@milkdown/kit/core";
import type { Ctx } from "@milkdown/kit/ctx";
import { clipboard } from "@milkdown/kit/plugin/clipboard";
import { history, redoCommand, undoCommand } from "@milkdown/kit/plugin/history";
import { listener, listenerCtx } from "@milkdown/kit/plugin/listener";
import {
  blockquoteSchema,
  bulletListSchema,
  commonmark,
  emphasisSchema,
  headingSchema,
  liftListItemCommand,
  linkSchema,
  listItemSchema,
  orderedListSchema,
  paragraphSchema,
  remarkPreserveEmptyLinePlugin,
  strongSchema,
  toggleEmphasisCommand,
  toggleStrongCommand,
  turnIntoTextCommand,
  wrapInBlockquoteCommand,
  wrapInBulletListCommand,
  wrapInHeadingCommand,
  wrapInOrderedListCommand,
} from "@milkdown/kit/preset/commonmark";
import { lift } from "@milkdown/kit/prose/commands";
import { Plugin, PluginKey, type EditorState, type Transaction } from "@milkdown/kit/prose/state";
import { $prose, getMarkdown } from "@milkdown/kit/utils";
import { Milkdown, MilkdownProvider, useEditor } from "@milkdown/react";
import { useEffect, useRef, useState } from "react";

import {
  applyLink,
  emptyToolbarState,
  linkRangeAtSelection,
  nearestList,
  readToolbarState,
  removeLink,
  switchListType,
  type MarkdownSchemaTypes,
  type MarkdownToolbarState,
} from "@/features/content/markdown-editor/markdown-editor-commands";
import {
  MarkdownEditorToolbar,
  type MarkdownToolbarAction,
} from "@/features/content/markdown-editor/markdown-editor-toolbar";
import {
  MarkdownLinkDialog,
  type MarkdownLinkDialogState,
} from "@/features/content/markdown-editor/markdown-link-dialog";
import type { MarkdownEditorProps } from "@/features/content/markdown-editor/markdown-editor-types";

// The preset writes empty paragraphs as a raw `<br />` placeholder. Published
// pages escape raw HTML, so that text would appear literally; empty
// paragraphs are left out of the Markdown instead.
const markdownPreset = commonmark.filter(
  (plugin) =>
    plugin !== remarkPreserveEmptyLinePlugin.plugin &&
    plugin !== remarkPreserveEmptyLinePlugin.options,
);

function schemaTypes(ctx: Ctx): MarkdownSchemaTypes {
  return {
    strong: strongSchema.type(ctx),
    emphasis: emphasisSchema.type(ctx),
    link: linkSchema.type(ctx),
    paragraph: paragraphSchema.type(ctx),
    heading: headingSchema.type(ctx),
    blockquote: blockquoteSchema.type(ctx),
    bulletList: bulletListSchema.type(ctx),
    orderedList: orderedListSchema.type(ctx),
    listItem: listItemSchema.type(ctx),
  };
}

type EditorAria = { labelId: string; describedBy?: string; invalid: boolean };

function editorAttributes(id: string, aria: EditorAria): Record<string, string> {
  const attributes: Record<string, string> = {
    id,
    class: "editor public-markdown markdown-editor-content",
    role: "textbox",
    "aria-multiline": "true",
    "aria-labelledby": aria.labelId,
    spellcheck: "true",
  };
  if (aria.describedBy) attributes["aria-describedby"] = aria.describedBy;
  if (aria.invalid) attributes["aria-invalid"] = "true";
  return attributes;
}

export function MilkdownMarkdownEditor(props: MarkdownEditorProps) {
  return (
    <MilkdownProvider>
      <MarkdownEditorSurface {...props} />
    </MilkdownProvider>
  );
}

function MarkdownEditorSurface({
  id,
  labelId,
  describedBy,
  invalid = false,
  initialValue,
  onChange,
  onReady,
}: MarkdownEditorProps) {
  const [toolbar, setToolbar] = useState<MarkdownToolbarState>(emptyToolbarState);
  const [linkDialog, setLinkDialog] = useState<MarkdownLinkDialogState | null>(null);
  const callbacks = useRef({ onChange, onReady });
  const aria = useRef<EditorAria>({ labelId, describedBy, invalid });
  const ctxRef = useRef<Ctx | null>(null);

  useEffect(() => {
    callbacks.current = { onChange, onReady };
  });

  const { loading } = useEditor(
    (root) =>
      Editor.make()
        .config((ctx) => {
          ctx.set(rootCtx, root);
          ctx.set(defaultValueCtx, initialValue);
          ctx.update(editorViewOptionsCtx, (previous) => ({
            ...previous,
            attributes: editorAttributes(id, aria.current),
          }));
          ctx
            .get(listenerCtx)
            .markdownUpdated((_ctx, markdown) => callbacks.current.onChange(markdown))
            .mounted((mountedCtx) => {
              ctxRef.current = mountedCtx;
              callbacks.current.onReady?.({
                normalizedInitialValue: getMarkdown()(mountedCtx),
                getMarkdown: () => {
                  try {
                    return getMarkdown()(mountedCtx);
                  } catch {
                    return null;
                  }
                },
              });
            })
            .destroy((destroyedCtx) => {
              // A development remount can destroy the previous editor after
              // the replacement mounts; only forget this editor's context.
              if (ctxRef.current === destroyedCtx) ctxRef.current = null;
            });
        })
        .use(markdownPreset)
        .use(history)
        .use(listener)
        .use(clipboard)
        .use(
          $prose((ctx) => {
            const types = schemaTypes(ctx);
            return new Plugin({
              key: new PluginKey("COMPASS_MARKDOWN_TOOLBAR"),
              view: (view) => {
                setToolbar(readToolbarState(view.state, types));
                return {
                  update: (updated) => setToolbar(readToolbarState(updated.state, types)),
                };
              },
            });
          }),
        ),
    [],
  );

  // Keep the textbox name, description, and invalid state current after
  // validation messages appear or clear.
  useEffect(() => {
    aria.current = { labelId, describedBy, invalid };
    const ctx = ctxRef.current;
    if (!ctx || loading) return;
    ctx.get(editorViewCtx).setProps({ attributes: editorAttributes(id, aria.current) });
  }, [describedBy, id, invalid, labelId, loading]);

  function withView(run: (ctx: Ctx) => void) {
    const ctx = ctxRef.current;
    if (!ctx) return;
    run(ctx);
    ctx.get(editorViewCtx).focus();
  }

  function dispatch(ctx: Ctx, command: (state: EditorState) => Transaction | null) {
    const view = ctx.get(editorViewCtx);
    const tr = command(view.state);
    if (tr) view.dispatch(tr.scrollIntoView());
  }

  function toggleList(ctx: Ctx, target: "bullet" | "ordered") {
    const types = schemaTypes(ctx);
    const commands = ctx.get(commandsCtx);
    const state = ctx.get(editorViewCtx).state;
    const targetType = target === "bullet" ? types.bulletList : types.orderedList;
    const list = nearestList(state, types);
    if (list?.node.type === targetType) commands.call(liftListItemCommand.key);
    else if (list) dispatch(ctx, (current) => switchListType(current, list, targetType, types));
    else commands.call(target === "bullet" ? wrapInBulletListCommand.key : wrapInOrderedListCommand.key);
  }

  function runAction(action: MarkdownToolbarAction) {
    if (action === "link") {
      const ctx = ctxRef.current;
      if (!ctx) return;
      const state = ctx.get(editorViewCtx).state;
      const existing = linkRangeAtSelection(state, schemaTypes(ctx).link);
      setLinkDialog({
        href: existing?.href ?? "",
        editing: existing !== null,
        needsText: existing === null && state.selection.empty,
      });
      return;
    }
    withView((ctx) => {
      const commands = ctx.get(commandsCtx);
      switch (action) {
        case "paragraph":
          commands.call(turnIntoTextCommand.key);
          break;
        case "heading-2":
          commands.call(wrapInHeadingCommand.key, 2);
          break;
        case "heading-3":
          commands.call(wrapInHeadingCommand.key, 3);
          break;
        case "bold":
          commands.call(toggleStrongCommand.key);
          break;
        case "italic":
          commands.call(toggleEmphasisCommand.key);
          break;
        case "bullet-list":
          toggleList(ctx, "bullet");
          break;
        case "ordered-list":
          toggleList(ctx, "ordered");
          break;
        case "blockquote": {
          const view = ctx.get(editorViewCtx);
          if (readToolbarState(view.state, schemaTypes(ctx)).blockquote) lift(view.state, view.dispatch);
          else commands.call(wrapInBlockquoteCommand.key);
          break;
        }
        case "undo":
          commands.call(undoCommand.key);
          break;
        case "redo":
          commands.call(redoCommand.key);
          break;
      }
    });
  }

  function focusEditor() {
    ctxRef.current?.get(editorViewCtx).focus();
  }

  return (
    <div className="rounded-md border border-border bg-surface-raised has-[.ProseMirror-focused]:border-focus has-[.ProseMirror-focused]:ring-2 has-[.ProseMirror-focused]:ring-focus/25">
      <MarkdownEditorToolbar
        controls={id}
        state={toolbar}
        disabled={loading}
        onAction={runAction}
      />
      <div className="max-h-[70vh] overflow-y-auto" aria-busy={loading}>
        <Milkdown />
        {loading ? <p className="sr-only">Loading the editor…</p> : null}
      </div>
      <MarkdownLinkDialog
        state={linkDialog}
        onClose={() => setLinkDialog(null)}
        onRestoreFocus={focusEditor}
        onApply={(href, text) => {
          const ctx = ctxRef.current;
          if (ctx) dispatch(ctx, (state) => applyLink(state, schemaTypes(ctx).link, href, text));
          setLinkDialog(null);
        }}
        onRemove={() => {
          const ctx = ctxRef.current;
          if (ctx) dispatch(ctx, (state) => removeLink(state, schemaTypes(ctx).link));
          setLinkDialog(null);
        }}
      />
    </div>
  );
}
