"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const NAVIGATION_DELAY_MS = 180;
const NAVIGATION_TIMEOUT_MS = 10_000;

function isModifiedClick(event: MouseEvent): boolean {
  return event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
}

export function NavigationProgress() {
  const pathname = usePathname();
  const [progressPathname, setProgressPathname] = useState<string | null>(null);
  const delayTimer = useRef<number | null>(null);
  const timeoutTimer = useRef<number | null>(null);

  useEffect(() => {
    if (delayTimer.current !== null) {
      window.clearTimeout(delayTimer.current);
      delayTimer.current = null;
    }
    if (timeoutTimer.current !== null) {
      window.clearTimeout(timeoutTimer.current);
      timeoutTimer.current = null;
    }
  }, [pathname]);

  useEffect(() => {
    const clearTimers = () => {
      if (delayTimer.current !== null) {
        window.clearTimeout(delayTimer.current);
        delayTimer.current = null;
      }
      if (timeoutTimer.current !== null) {
        window.clearTimeout(timeoutTimer.current);
        timeoutTimer.current = null;
      }
    };

    const handleClick = (event: MouseEvent) => {
      if (event.defaultPrevented || isModifiedClick(event)) {
        return;
      }

      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }

      const anchor = target.closest("a");
      if (!(anchor instanceof HTMLAnchorElement)) {
        return;
      }

      if (
        anchor.target && anchor.target !== "_self" ||
        anchor.hasAttribute("download") ||
        anchor.getAttribute("href")?.startsWith("#")
      ) {
        return;
      }

      const destination = new URL(anchor.href, window.location.href);
      if (
        destination.origin !== window.location.origin ||
        destination.pathname === window.location.pathname
      ) {
        return;
      }

      clearTimers();
      delayTimer.current = window.setTimeout(() => {
        const startedPathname = window.location.pathname;
        setProgressPathname(startedPathname);
        timeoutTimer.current = window.setTimeout(() => {
          setProgressPathname((currentPathname) =>
            currentPathname === startedPathname ? null : currentPathname,
          );
          timeoutTimer.current = null;
        }, NAVIGATION_TIMEOUT_MS);
      }, NAVIGATION_DELAY_MS);
    };

    document.addEventListener("click", handleClick);
    return () => {
      document.removeEventListener("click", handleClick);
      clearTimers();
    };
  }, []);

  if (progressPathname !== pathname) {
    return null;
  }

  return (
    <div
      className="compass-navigation-progress"
      role="progressbar"
      aria-label="Loading next page"
      aria-valuemin={0}
      aria-valuemax={100}
    />
  );
}
