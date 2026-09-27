"use client";

import {
  Bold,
  ChevronDown,
  Italic,
  Link2,
  List,
  ListOrdered,
  Quote,
  Redo2,
  Undo2,
  type LucideIcon,
} from "lucide-react";
import { useRef, useState, type KeyboardEvent } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { MarkdownToolbarState } from "@/features/content/markdown-editor/markdown-editor-commands";
import { cn } from "@/lib/utils/cn";

export type MarkdownToolbarAction =
  | "paragraph"
  | "heading-2"
  | "heading-3"
  | "bold"
  | "italic"
  | "link"
  | "bullet-list"
  | "ordered-list"
  | "blockquote"
  | "undo"
  | "redo";

type BlockAction = Extract<MarkdownToolbarAction, "paragraph" | "heading-2" | "heading-3">;

type ToolbarButton = {
  action: Exclude<MarkdownToolbarAction, BlockAction>;
  label: string;
  icon: LucideIcon;
  pressed?: boolean;
  enabled?: boolean;
  separatorBefore?: boolean;
};

const buttonClass =
  "inline-flex min-h-9 min-w-9 items-center justify-center gap-1 rounded-md px-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-45 aria-pressed:bg-brand-subtle aria-pressed:text-brand";

function blockLabel(state: MarkdownToolbarState): string {
  if (state.block.kind === "paragraph") return "Paragraph";
  if (state.block.kind === "heading") return `Heading ${state.block.level}`;
  return "Text style";
}

export function MarkdownEditorToolbar({
  controls,
  state,
  disabled,
  onAction,
}: {
  controls: string;
  state: MarkdownToolbarState;
  disabled: boolean;
  onAction: (action: MarkdownToolbarAction) => void;
}) {
  const toolbarRef = useRef<HTMLDivElement>(null);
  const pendingBlockAction = useRef<BlockAction | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const buttons: ToolbarButton[] = [
    { action: "bold", label: "Bold", icon: Bold, pressed: state.bold, separatorBefore: true },
    { action: "italic", label: "Italic", icon: Italic, pressed: state.italic },
    { action: "link", label: state.link ? "Edit link" : "Add link", icon: Link2, pressed: state.link },
    { action: "bullet-list", label: "Bulleted list", icon: List, pressed: state.bulletList, separatorBefore: true },
    { action: "ordered-list", label: "Numbered list", icon: ListOrdered, pressed: state.orderedList },
    { action: "blockquote", label: "Blockquote", icon: Quote, pressed: state.blockquote },
    { action: "undo", label: "Undo", icon: Undo2, enabled: state.canUndo, separatorBefore: true },
    { action: "redo", label: "Redo", icon: Redo2, enabled: state.canRedo },
  ];
  // Index 0 is the text style menu; buttons follow it.
  const enabledAt = (index: number) => index === 0 || buttons[index - 1]?.enabled !== false;
  const tabStop = enabledAt(activeIndex) ? activeIndex : 0;

  // One tab stop for the toolbar; arrow keys, Home, and End move between controls.
  function moveFocus(event: KeyboardEvent<HTMLDivElement>) {
    const all = Array.from(toolbarRef.current?.querySelectorAll<HTMLElement>("[data-toolbar-control]") ?? []);
    const items = all.filter((item) => !item.hasAttribute("disabled"));
    const current = items.findIndex((item) => item === document.activeElement);
    if (current < 0) return;
    let next: number;
    if (event.key === "ArrowRight") next = (current + 1) % items.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + items.length) % items.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    else return;
    event.preventDefault();
    const target = items[next];
    setActiveIndex(all.indexOf(target));
    target.focus();
  }

  return (
    <div
      ref={toolbarRef}
      role="toolbar"
      aria-label="Body formatting"
      aria-controls={controls}
      onKeyDown={moveFocus}
      className="flex flex-wrap items-center gap-0.5 border-b border-border px-2 py-1.5"
    >
      <DropdownMenu>
        <DropdownMenuTrigger asChild disabled={disabled}>
          <button
            type="button"
            data-toolbar-control=""
            tabIndex={tabStop === 0 ? 0 : -1}
            onFocus={() => setActiveIndex(0)}
            className={cn(buttonClass, "min-w-32 justify-between px-2.5 font-medium")}
            aria-label={`Text style: ${blockLabel(state)}`}
          >
            <span aria-hidden="true">{blockLabel(state)}</span>
            <ChevronDown size={15} aria-hidden="true" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          className="min-w-44"
          onCloseAutoFocus={(event) => {
            // Apply the chosen style after the menu releases focus so the
            // editor, not the menu button, receives it.
            const action = pendingBlockAction.current;
            pendingBlockAction.current = null;
            if (!action) return;
            event.preventDefault();
            onAction(action);
          }}
        >
          <DropdownMenuItem onSelect={() => { pendingBlockAction.current = "paragraph"; }}>
            Paragraph
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => { pendingBlockAction.current = "heading-2"; }}>
            <span className="font-heading text-base font-bold">Heading 2</span>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => { pendingBlockAction.current = "heading-3"; }}>
            <span className="font-heading font-bold">Heading 3</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {buttons.map((button, position) => {
        const index = position + 1;
        const Icon = button.icon;
        return (
          <span key={button.action} className="contents">
            {button.separatorBefore ? <span aria-hidden="true" className="mx-1 h-6 w-px bg-border" /> : null}
            <button
              type="button"
              data-toolbar-control=""
              tabIndex={tabStop === index ? 0 : -1}
              onFocus={() => setActiveIndex(index)}
              className={buttonClass}
              aria-label={button.label}
              aria-pressed={button.pressed}
              title={button.label}
              disabled={disabled || button.enabled === false}
              // Keep the editor selection while clicking toolbar buttons.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onAction(button.action)}
            >
              <Icon size={17} aria-hidden="true" />
            </button>
          </span>
        );
      })}
    </div>
  );
}
