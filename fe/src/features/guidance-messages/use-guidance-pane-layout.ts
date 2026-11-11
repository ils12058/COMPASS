"use client";

import { useLayoutEffect, type RefObject } from "react";

/** Reserve the actual controls plus a small history region, even when Safari cannot size an
 * intrinsic grid minimum. Short viewports then scroll the document (or the existing drawer).
 * Only CSS dimensions change; the composer and its send intent stay mounted. */
export function useGuidancePaneLayout(ref: RefObject<HTMLDivElement | null>) {
  useLayoutEffect(() => {
    const pane = ref.current;
    const layout = pane?.closest<HTMLElement>("[data-guidance-layout]");
    if (!pane || !layout) return;
    const measure = () => {
      const controls = Array.from(pane.querySelectorAll<HTMLElement>("[data-guidance-fixed]"));
      const height = controls.reduce((total, node) => {
        const style = getComputedStyle(node);
        return total + node.getBoundingClientRect().height + parseFloat(style.marginTop || "0") + parseFloat(style.marginBottom || "0");
      }, 0);
      layout.style.setProperty("--guidance-controls-height", `${Math.ceil(height) + 2}px`);
    };
    const sizes = new ResizeObserver(measure);
    const observe = () => {
      sizes.disconnect();
      sizes.observe(pane);
      pane.querySelectorAll<HTMLElement>("[data-guidance-fixed]").forEach((node) => sizes.observe(node));
      measure();
    };
    const content = new MutationObserver(observe);
    content.observe(pane, { childList: true, subtree: true });
    observe();
    return () => {
      sizes.disconnect();
      content.disconnect();
      layout.style.removeProperty("--guidance-controls-height");
    };
  }, [ref]);
}
