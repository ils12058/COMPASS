"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils/cn";

// UCN Guidance and Counseling Office activity photographs: wide shots, no one-to-one counseling.
const PHOTOS = [
  { src: "/brand/hero-gym-seminar.webp", position: "object-[50%_62%]" },
  { src: "/brand/hero-classroom.webp", position: "object-[50%_55%]" },
] as const;

// The photo fills the hero's right side on wider screens and its full width on phones.
const SIZES = "(min-width: 640px) 66vw, 100vw";
const layer = "object-cover transition-opacity duration-1000 ease-in-out motion-reduce:transition-none";

/**
 * The hero's faded backdrop. The first photo is the page's largest paint, so it alone is preloaded.
 * The second is requested only after the page has loaded, and only on wider screens; it never
 * shows before it has decoded. `second` follows the headline rotation, so the headline's
 * Pause/Play, reduced-motion start, hidden-tab and hover/focus holds govern the photos too.
 */
export function HeroBackdrop({ second }: { second: boolean }) {
  const [requestSecond, setRequestSecond] = useState(false);
  const [secondReady, setSecondReady] = useState(false);

  useEffect(() => {
    // Phones keep one photo: the backdrop is faint there, and their data is not ours to spend.
    if (!window.matchMedia("(min-width: 640px)").matches) return;
    const start = () => setRequestSecond(true);
    if (document.readyState === "complete") {
      start();
      return;
    }
    window.addEventListener("load", start, { once: true });
    return () => window.removeEventListener("load", start);
  }, []);

  const showSecond = second && secondReady;
  return (
    <div className="public-hero-campus absolute inset-y-0 right-0 -z-10 w-full sm:w-[66%]" aria-hidden="true">
      <Image
        src={PHOTOS[0].src}
        alt=""
        fill
        preload
        fetchPriority="high"
        sizes={SIZES}
        className={cn(layer, PHOTOS[0].position, showSecond ? "opacity-0" : "opacity-100")}
        data-hero-photo="0"
      />
      {requestSecond ? (
        <Image
          src={PHOTOS[1].src}
          alt=""
          fill
          sizes={SIZES}
          onLoad={() => setSecondReady(true)}
          className={cn(layer, PHOTOS[1].position, showSecond ? "opacity-100" : "opacity-0")}
          data-hero-photo="1"
        />
      ) : null}
    </div>
  );
}
