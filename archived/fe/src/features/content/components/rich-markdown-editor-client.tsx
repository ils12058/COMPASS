"use client";

import { Crepe } from "@milkdown/crepe";
import { commandsCtx, editorViewCtx } from "@milkdown/kit/core";
import {
  blockquoteSchema,
  bulletListSchema,
  headingSchema,
  insertHrCommand,
  linkSchema,
  orderedListSchema,
  strongSchema,
  emphasisSchema,
  toggleEmphasisCommand,
  toggleLinkCommand,
  toggleStrongCommand,
  turnIntoTextCommand,
  wrapInBlockquoteCommand,
  wrapInBulletListCommand,
  wrapInHeadingCommand,
  wrapInOrderedListCommand,
} from "@milkdown/kit/preset/commonmark";
import { redo, undo } from "@milkdown/kit/prose/history";
import {
  Bold,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Minus,
  Quote,
  Redo2,
  Undo2,
} from "lucide-react";
import {
  type MouseEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import "@milkdown/crepe/theme/common/style.css";
import "@milkdown/crepe/theme/frame.css";
import "@/features/content/components/rich-markdown-editor.css";

type BlockStyle = "paragraph" | "heading-2" | "heading-3";

type ActiveState = {
  bold: boolean;
  italic: boolean;
  link: boolean;
  quote: boolean;
  bulletList: boolean;
  orderedList: boolean;
  blockStyle: BlockStyle;
};

const EMPTY_ACTIVE: ActiveState = {
  bold: false,
  italic: false,
  link: false,
  quote: false,
  bulletList: false,
  orderedList: false,
  blockStyle: "paragraph",
};

function safeLink(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  if (trimmed.startsWith("/") || trimmed.startsWith("#") || trimmed.startsWith("?")) {
    return trimmed;
  }

  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? trimmed : null;
  } catch {
    return null;
  }
}

export function RichMarkdownEditorClient({
  initialValue,
  onChange,
  disabled,
  ariaLabel,
}: {
  initialValue: string;
  onChange: (markdown: string) => void;
  disabled: boolean;
  ariaLabel: string;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const crepeRef = useRef<Crepe | null>(null);
  const initialValueRef = useRef(initialValue);
  const initialDisabledRef = useRef(disabled);
  const onChangeRef = useRef(onChange);
  const ariaLabelRef = useRef(ariaLabel);
  const [ready, setReady] = useState(false);
  const [active, setActive] = useState<ActiveState>(EMPTY_ACTIVE);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const refreshActiveState = useCallback(() => {
    const crepe = crepeRef.current;
    if (!crepe) {
      return;
    }

    setActive(
      crepe.editor.action((ctx) => {
        const view = ctx.get(editorViewCtx);
        const { state } = view;
        const marks = state.storedMarks ?? state.selection.$from.marks();
        const markActive = (type: ReturnType<typeof strongSchema.type>) =>
          marks.some((mark) => mark.type === type);

        let quote = false;
        let bulletList = false;
        let orderedList = false;
        for (let depth = state.selection.$from.depth; depth >= 0; depth -= 1) {
          const type = state.selection.$from.node(depth).type;
          quote ||= type === blockquoteSchema.type(ctx);
          bulletList ||= type === bulletListSchema.type(ctx);
          orderedList ||= type === orderedListSchema.type(ctx);
        }

        const parent = state.selection.$from.parent;
        let blockStyle: BlockStyle = "paragraph";
        if (parent.type === headingSchema.type(ctx)) {
          blockStyle = parent.attrs.level === 3 ? "heading-3" : "heading-2";
        }

        return {
          bold: markActive(strongSchema.type(ctx)),
          italic: markActive(emphasisSchema.type(ctx)),
          link: markActive(linkSchema.type(ctx)),
          quote,
          bulletList,
          orderedList,
          blockStyle,
        };
      }),
    );
  }, []);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) {
      return;
    }

    let cancelled = false;
    const crepe = new Crepe({
      root,
      defaultValue: initialValueRef.current,
      features: {
        [Crepe.Feature.ImageBlock]: false,
        [Crepe.Feature.CodeMirror]: false,
        [Crepe.Feature.Table]: false,
        [Crepe.Feature.Latex]: false,
        [Crepe.Feature.AI]: false,
        [Crepe.Feature.BlockEdit]: false,
        [Crepe.Feature.Toolbar]: false,
        [Crepe.Feature.TopBar]: false,
      },
      featureConfigs: {
        [Crepe.Feature.Placeholder]: {
          text: "Write content…",
          mode: "doc",
        },
      },
    });
    crepeRef.current = crepe;

    crepe.on((listener) => {
      listener.markdownUpdated((_ctx, markdown, previousMarkdown) => {
        if (markdown !== previousMarkdown) {
          onChangeRef.current(markdown);
        }
        window.requestAnimationFrame(refreshActiveState);
      });
    });

    void crepe.create().then(() => {
      if (cancelled) {
        return;
      }

      crepe.setReadonly(initialDisabledRef.current);
      const editable = root.querySelector<HTMLElement>('[contenteditable="true"]');
      if (editable) {
        editable.setAttribute("role", "textbox");
        editable.setAttribute("aria-multiline", "true");
        editable.setAttribute("aria-label", ariaLabelRef.current);
      }
      setReady(true);
      refreshActiveState();
    });

    const refresh = () => window.requestAnimationFrame(refreshActiveState);
    root.addEventListener("keyup", refresh);
    root.addEventListener("mouseup", refresh);
    root.addEventListener("focusin", refresh);
    const handlePaste = (event: ClipboardEvent) => {
        const clipboard = event.clipboardData;
        if (!clipboard) {
          return;
        }
        const hasImageFile = Array.from(clipboard.files).some((file) =>
          file.type.startsWith("image/"),
        );
        const html = clipboard.getData("text/html");
        if (!hasImageFile && !/<img\b/i.test(html)) {
          return;
        }

        event.preventDefault();
        const plainText = clipboard.getData("text/plain");
        if (!plainText) {
          return;
        }
        crepe.editor.action((ctx) => {
          const view = ctx.get(editorViewCtx);
          view.dispatch(view.state.tr.insertText(plainText));
          view.focus();
        });
      };
    const handleDrop = (event: DragEvent) => {
      if (event.dataTransfer?.files.length) {
        event.preventDefault();
      }
    };
    root.addEventListener("paste", handlePaste, true);
    root.addEventListener("drop", handleDrop, true);

    return () => {
      cancelled = true;
      root.removeEventListener("keyup", refresh);
      root.removeEventListener("mouseup", refresh);
      root.removeEventListener("focusin", refresh);
      root.removeEventListener("paste", handlePaste, true);
      root.removeEventListener("drop", handleDrop, true);
      crepeRef.current = null;
      void crepe.destroy();
    };
  }, [refreshActiveState]);

  useEffect(() => {
    crepeRef.current?.setReadonly(disabled);
  }, [disabled]);

  function runCommand(
    command:
      | typeof toggleStrongCommand
      | typeof toggleEmphasisCommand
      | typeof wrapInBlockquoteCommand
      | typeof wrapInBulletListCommand
      | typeof wrapInOrderedListCommand
      | typeof insertHrCommand
      | typeof turnIntoTextCommand,
  ) {
    const crepe = crepeRef.current;
    if (!crepe || disabled) {
      return;
    }

    crepe.editor.action((ctx) => {
      const manager = ctx.get(commandsCtx);
      manager.call(command.key);
      ctx.get(editorViewCtx).focus();
    });
    window.requestAnimationFrame(refreshActiveState);
  }

  function setBlockStyle(value: BlockStyle) {
    const crepe = crepeRef.current;
    if (!crepe || disabled) {
      return;
    }

    crepe.editor.action((ctx) => {
      const manager = ctx.get(commandsCtx);
      if (value === "paragraph") {
        manager.call(turnIntoTextCommand.key);
      } else {
        manager.call(wrapInHeadingCommand.key, value === "heading-2" ? 2 : 3);
      }
      ctx.get(editorViewCtx).focus();
    });
    window.requestAnimationFrame(refreshActiveState);
  }

  function editLink() {
    const crepe = crepeRef.current;
    if (!crepe || disabled) {
      return;
    }

    const entered = window.prompt("Enter an http(s), relative, or page link:");
    if (entered === null) {
      return;
    }

    const href = safeLink(entered);
    if (!href) {
      window.alert("Enter a valid web or COMPASS link.");
      return;
    }

    crepe.editor.action((ctx) => {
      ctx.get(commandsCtx).call(toggleLinkCommand.key, { href });
      ctx.get(editorViewCtx).focus();
    });
    window.requestAnimationFrame(refreshActiveState);
  }

  function history(action: "undo" | "redo") {
    const crepe = crepeRef.current;
    if (!crepe || disabled) {
      return;
    }

    crepe.editor.action((ctx) => {
      const view = ctx.get(editorViewCtx);
      (action === "undo" ? undo : redo)(view.state, view.dispatch);
      view.focus();
    });
    window.requestAnimationFrame(refreshActiveState);
  }

  return (
    <div className="compass-rich-editor rounded-xl border bg-card">
      <div
        role="toolbar"
        aria-label="Content formatting"
        className="flex flex-wrap items-center gap-1 border-b bg-muted/40 p-2"
      >
        <label className="sr-only" htmlFor="content-block-style">
          Text style
        </label>
        <select
          id="content-block-style"
          aria-label="Text style"
          value={active.blockStyle}
          disabled={disabled || !ready}
          onChange={(event) => setBlockStyle(event.target.value as BlockStyle)}
          className="mr-1 min-h-9 rounded-md border bg-card px-2 text-sm"
        >
          <option value="paragraph">Paragraph</option>
          <option value="heading-2">Section heading</option>
          <option value="heading-3">Subheading</option>
        </select>

        <ToolbarButton
          label="Bold"
          pressed={active.bold}
          disabled={disabled || !ready}
          onClick={() => runCommand(toggleStrongCommand)}
        >
          <Bold aria-hidden="true" className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          label="Italic"
          pressed={active.italic}
          disabled={disabled || !ready}
          onClick={() => runCommand(toggleEmphasisCommand)}
        >
          <Italic aria-hidden="true" className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          label="Bulleted list"
          pressed={active.bulletList}
          disabled={disabled || !ready}
          onClick={() => runCommand(wrapInBulletListCommand)}
        >
          <List aria-hidden="true" className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          label="Numbered list"
          pressed={active.orderedList}
          disabled={disabled || !ready}
          onClick={() => runCommand(wrapInOrderedListCommand)}
        >
          <ListOrdered aria-hidden="true" className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          label="Link"
          pressed={active.link}
          disabled={disabled || !ready}
          onClick={editLink}
        >
          <LinkIcon aria-hidden="true" className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          label="Block quote"
          pressed={active.quote}
          disabled={disabled || !ready}
          onClick={() => runCommand(wrapInBlockquoteCommand)}
        >
          <Quote aria-hidden="true" className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          label="Horizontal rule"
          disabled={disabled || !ready}
          onClick={() => runCommand(insertHrCommand)}
        >
          <Minus aria-hidden="true" className="size-4" />
        </ToolbarButton>
        <span className="mx-1 h-6 w-px bg-border" aria-hidden="true" />
        <ToolbarButton
          label="Undo"
          disabled={disabled || !ready}
          onClick={() => history("undo")}
        >
          <Undo2 aria-hidden="true" className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          label="Redo"
          disabled={disabled || !ready}
          onClick={() => history("redo")}
        >
          <Redo2 aria-hidden="true" className="size-4" />
        </ToolbarButton>
      </div>
      <div ref={rootRef} className="min-h-64" aria-busy={!ready} />
    </div>
  );
}

function ToolbarButton({
  label,
  pressed,
  disabled,
  onClick,
  children,
}: {
  label: string;
  pressed?: boolean;
  disabled: boolean;
  onClick: (event: MouseEvent<HTMLButtonElement>) => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      disabled={disabled}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className="inline-flex size-9 items-center justify-center rounded-md border border-transparent text-foreground hover:border-border hover:bg-card aria-pressed:border-[var(--compass-support)] aria-pressed:bg-accent disabled:opacity-50"
    >
      {children}
    </button>
  );
}
