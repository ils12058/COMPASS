"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useReducedMotion } from "@/features/accessibility/use-accessibility-preferences";
import { orientationSteps, type GuideStep } from "./guide-steps";

type Placement = { left: number; top: number; width: number; height: number; panelLeft: number; panelWidth: number; panelHeight: number; bottom: number };

export function OrientationGuide({ root, opener, onFinish }: {
  root: RefObject<HTMLDivElement | null>; opener: HTMLElement; onFinish: (completed: boolean) => void;
}) {
  const reducedMotion = useReducedMotion();
  const [steps, setSteps] = useState<GuideStep[]>([]);
  const [index, setIndex] = useState(0);
  const [placement, setPlacement] = useState<Placement | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [panelNode, setPanelNode] = useState<HTMLDivElement | null>(null);
  const bindPanel = useCallback((node: HTMLDivElement | null) => { panel.current = node; setPanelNode(node); }, []);
  const stepDescription = useId();
  const restoreRequested = useRef(true);
  const explicitClose = useRef(false);
  const finish = useRef(onFinish);
  useEffect(() => { finish.current = onFinish; }, [onFinish]);
  const step = steps[Math.min(index, steps.length - 1)];
  const target = step?.target;
  const stepId = step?.id;
  const placed = placement !== null;

  useEffect(() => {
    const surface = root.current;
    if (!surface) return;
    const update = () => {
      const available = orientationSteps(surface);
      setSteps(available);
      if (!available.length) {
        finish.current(false);
        // With no target the panel never mounts, so its close autofocus cannot return focus.
        if (opener.isConnected) opener.focus({ preventScroll: true });
      }
    };
    const frame = requestAnimationFrame(update);
    window.addEventListener("resize", update);
    const observer = new MutationObserver(() => {
      // A new modal or menu takes priority. No other overlay is opened or closed by this guide.
      if (document.querySelector('[aria-modal="true"], [role="menu"], [popover]:popover-open, dialog[open]')) finish.current(false);
      else update();
    });
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden", "aria-expanded", "aria-modal", "open", "data-state", "data-orientation"] });
    const onToggle = () => { if (document.querySelector('[popover]:popover-open, dialog[open]')) finish.current(false); };
    document.addEventListener("toggle", onToggle, true);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener("resize", update); document.removeEventListener("toggle", onToggle, true); };
  }, [opener, root]);

  useEffect(() => {
    if (!target) return;
    target.scrollIntoView({ block: "start", inline: "nearest", behavior: reducedMotion ? "instant" : "smooth" });
    const measure = () => {
      const viewport = window.visualViewport;
      const x = viewport?.offsetLeft ?? 0;
      const y = viewport?.offsetTop ?? 0;
      const width = viewport?.width ?? innerWidth;
      const height = viewport?.height ?? innerHeight;
      const rect = target.getBoundingClientRect();
      const gap = 12;
      const panelWidth = Math.min(28 * parseFloat(getComputedStyle(document.documentElement).fontSize), width - gap * 2);
      const left = Math.max(x + 4, rect.left - 4);
      const top = Math.max(y + 4, rect.top - 4);
      setPlacement({ left, top, width: Math.max(0, Math.min(rect.right + 4, x + width - 4) - left),
        height: Math.max(0, Math.min(rect.bottom + 4, y + height - 4) - top),
        panelLeft: x + width - panelWidth - gap, panelWidth,
        // In short/enlarged layouts the whole panel scrolls, keeping the actual target clear.
        panelHeight: Math.max(80, height - Math.max(gap, rect.bottom - y + gap) - gap), bottom: innerHeight - y - height + gap });
    };
    const frame = requestAnimationFrame(measure);
    const observer = new ResizeObserver(measure);
    observer.observe(target);
    if (panel.current) observer.observe(panel.current);
    window.addEventListener("scroll", measure, true);
    window.addEventListener("resize", measure);
    window.visualViewport?.addEventListener("resize", measure);
    window.visualViewport?.addEventListener("scroll", measure);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener("scroll", measure, true); window.removeEventListener("resize", measure); window.visualViewport?.removeEventListener("resize", measure); window.visualViewport?.removeEventListener("scroll", measure); };
  }, [stepId, target, reducedMotion]);

  useLayoutEffect(() => {
    if (!placed || !target || !panelNode) return;
    // Place the visible panel before focusing it. WebKit cannot focus a hidden control.
    panelNode.querySelector<HTMLButtonElement>("[data-orientation-next]")?.focus();
  }, [placed, stepId, target, panelNode]);

  function restoreFocus() {
    requestAnimationFrame(() => {
      // Explicit dismissal restores the opener in WebKit even if it left focus on the page.
      // Outside interaction and another dialog/menu retain their own focus ownership.
      if ((!restoreRequested.current && !explicitClose.current) || document.querySelector('[aria-modal="true"], [role="menu"], [popover]:popover-open, dialog[open], [data-orientation-panel][data-state="open"]')) return;
      const fallback = root.current?.querySelector<HTMLElement>('[data-orientation="guide-launch"]');
      (opener.isConnected && opener.getClientRects().length ? opener : fallback)?.focus();
    });
  }

  function dismiss(completed: boolean) { explicitClose.current = true; onFinish(completed); }

  return <Dialog open modal={false} onOpenChange={open => { if (!open) onFinish(false); }}>
    {placement ? <div aria-hidden="true" data-orientation-highlight="" className="pointer-events-none fixed z-50 rounded-md border-2 border-brand"
      style={{ left: placement.left, top: placement.top, width: placement.width, height: placement.height }} /> : null}
    {placement && step ? <DialogContent ref={bindPanel} aria-modal={false} data-orientation-panel="" closeLabel="Exit guide"
      className="left-auto top-auto max-w-none translate-x-0 translate-y-0 p-4 transition-none sm:p-5"
      style={{ left: placement.panelLeft, bottom: placement.bottom, width: placement.panelWidth, maxHeight: placement.panelHeight }}
      onOpenAutoFocus={event => { event.preventDefault(); }}
      onEscapeKeyDown={() => { explicitClose.current = true; }}
      onInteractOutside={() => { restoreRequested.current = false; }}
      onCloseAutoFocus={event => { event.preventDefault(); restoreFocus(); }}>
      <DialogTitle>Getting around COMPASS</DialogTitle>
      <DialogDescription className="sr-only">An optional guide to Home and the portal controls. Escape exits the guide.</DialogDescription>
      {step ? <>
        <div id={stepDescription}>
          <p className="mt-3 text-sm text-muted">Step {Math.min(index + 1, steps.length)} of {steps.length}</p>
          <h2 className="mt-1 font-heading text-lg font-semibold text-brand">{step.title}</h2>
          <p className="mt-2 text-sm leading-6 text-ink">{step.description}</p>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button variant="secondary" disabled={index === 0} onClick={() => setIndex(value => Math.max(0, value - 1))}>Back</Button>
          {index >= steps.length - 1 ? <Button data-orientation-next="" aria-describedby={stepDescription} onClick={() => dismiss(true)}>Finish guide</Button>
            : <Button data-orientation-next="" aria-describedby={stepDescription} onClick={() => setIndex(value => Math.min(steps.length - 1, value + 1))}>Next</Button>}
          <Button variant="quiet" onClick={() => dismiss(false)}>Skip guide</Button>
        </div>
      </> : null}
    </DialogContent> : null}
  </Dialog>;
}
