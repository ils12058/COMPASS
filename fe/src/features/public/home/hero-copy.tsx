"use client";

import { ArrowRight, Pause, Play } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { useReducedMotion } from "@/features/accessibility/use-accessibility-preferences";
import { cn } from "@/lib/utils/cn";

// Long enough to read either headline before the other one fades in.
const HEADLINE_INTERVAL_MS = 7000;

function subscribeToVisibility(onChange: () => void) {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
}

// The outgoing headline fades out before the incoming one fades in, so the two never overlap.
const headlineLayer = "col-start-1 row-start-1 transition-opacity motion-reduce:delay-0";
const shownLayer = "opacity-100 duration-500 delay-300";
const hiddenLayer = "opacity-0 duration-300";

type Playback = "auto" | "playing" | "paused";

export function HeroCopy() {
  // Covers both the operating-system setting and the COMPASS "Reduce motion" setting.
  const prefersReducedMotion = useReducedMotion();
  const pageVisible = useSyncExternalStore(
    subscribeToVisibility,
    () => document.visibilityState === "visible",
    () => true,
  );
  const toggleRef = useRef<HTMLButtonElement>(null);
  const [playback, setPlayback] = useState<Playback>("auto");
  const [hoverHold, setHoverHold] = useState(false);
  const [focusHold, setFocusHold] = useState(false);
  const [showQuote, setShowQuote] = useState(false);

  // Reduced motion starts paused; the toggle's explicit choice always wins.
  const wantsRotation =
    playback === "playing" || (playback === "auto" && !prefersReducedMotion);
  // Reading (hover) or working inside the hero (keyboard focus) holds the current headline.
  const rotating = pageVisible && wantsRotation && !hoverHold && !focusHold;

  useEffect(() => {
    if (!rotating) return;
    const timer = window.setTimeout(
      () => setShowQuote((current) => !current),
      HEADLINE_INTERVAL_MS,
    );
    return () => window.clearTimeout(timer);
  }, [rotating, showQuote]);

  return (
    <div
      className="max-w-2xl"
      onPointerEnter={(event) => {
        if (event.pointerType === "mouse") setHoverHold(true);
      }}
      onPointerLeave={(event) => {
        if (event.pointerType === "mouse") setHoverHold(false);
      }}
      onFocus={(event) => setFocusHold(!toggleRef.current?.contains(event.target))}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setFocusHold(false);
      }}
    >
      <p className="font-heading text-sm font-bold tracking-[0.2em] text-on-brand/80">COMPASS</p>
      {/* Both headlines share one grid cell, so the hero keeps the taller one's height. */}
      <div className="mt-4 grid">
        <h1
          className={cn(
            headlineLayer,
            "font-heading text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl",
            showQuote ? hiddenLayer : shownLayer,
          )}
        >
          Counseling Office Management Platform and Student Services
        </h1>
        <p
          className={cn(
            headlineLayer,
            "self-center font-script text-5xl font-semibold leading-[1.05] sm:text-6xl lg:text-7xl",
            showQuote ? shownLayer : hiddenLayer,
          )}
        >
          You don’t have to{" "}
          <span className="whitespace-nowrap underline decoration-gold decoration-[0.07em] underline-offset-[0.14em]">
            find your way
          </span>{" "}
          alone.
        </p>
      </div>
      <p className="mt-6 max-w-xl text-base leading-7 text-on-brand/85 sm:text-lg">
        The online platform of the UCN Guidance and Counseling Office.
      </p>
      <div className="mt-8 flex items-center gap-3">
        <Link
          href="/login"
          className="inline-flex min-h-11 items-center gap-2 rounded-md border border-on-brand bg-on-brand px-5 py-2.5 text-sm font-bold text-brand-strong transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand focus-visible:ring-offset-2 focus-visible:ring-offset-brand-strong"
        >
          Sign in to COMPASS
          <ArrowRight size={18} aria-hidden="true" />
        </Link>
        <button
          ref={toggleRef}
          type="button"
          onClick={() => setPlayback(wantsRotation ? "paused" : "playing")}
          aria-label={wantsRotation ? "Pause headline animation" : "Play headline animation"}
          title={wantsRotation ? "Pause headline animation" : "Play headline animation"}
          className="inline-flex size-11 items-center justify-center rounded-md border border-on-brand/35 text-on-brand/80 transition-colors hover:bg-on-brand/10 hover:text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand focus-visible:ring-offset-2 focus-visible:ring-offset-brand-strong"
        >
          {wantsRotation ? (
            <Pause size={16} aria-hidden="true" />
          ) : (
            <Play size={16} aria-hidden="true" />
          )}
        </button>
      </div>
    </div>
  );
}
