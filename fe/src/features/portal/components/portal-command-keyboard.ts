type ShortcutEvent = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "repeat" | "isComposing" | "defaultPrevented">;

export function isPortalCommandShortcut(event: ShortcutEvent): boolean {
  return event.key.toLowerCase() === "k" && event.ctrlKey !== event.metaKey &&
    !event.altKey && !event.shiftKey && !event.repeat && !event.isComposing && !event.defaultPrevented;
}

export function hasOtherPortalModal(document: Document, ownDialog: HTMLElement | null): boolean {
  // Radix dialogs and confirmations carry data-state; FloatingListTools uses native <dialog>.
  return [...document.querySelectorAll('[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"], dialog[open]')]
    .some((element) => element !== ownDialog);
}

export function registerPortalCommandShortcut(
  toggle: () => void,
  ownDialog: () => HTMLElement | null,
  browser: Pick<Window, "addEventListener" | "removeEventListener"> = window,
  page: Document = document,
): () => void {
  function onKeyDown(event: KeyboardEvent) {
    if (!isPortalCommandShortcut(event) || hasOtherPortalModal(page, ownDialog())) return;
    event.preventDefault();
    toggle();
  }
  browser.addEventListener("keydown", onKeyDown);
  return () => browser.removeEventListener("keydown", onKeyDown);
}

export function nextActiveCommandIndex(current: number, direction: "up" | "down", count: number): number {
  if (!count) return -1;
  return (current + (direction === "down" ? 1 : -1) + count) % count;
}
