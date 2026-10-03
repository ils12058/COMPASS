import Image from "next/image";

import { HeroCopy } from "@/features/public/home/hero-copy";

export function PublicHero() {
  return (
    <section className="public-hero relative isolate overflow-hidden text-on-brand">
      <div className="public-hero-campus absolute inset-y-0 right-0 -z-10 w-full sm:w-[66%]" aria-hidden="true" />
      <div className="absolute inset-0 -z-20 bg-brand-strong/10" aria-hidden="true" />
      {/* An introduction rather than a whole first screen: on desktop the hero leaves room for
          the announcements, quick access, and resources below it, and stops at 31rem. */}
      <div className="mx-auto grid max-w-6xl gap-6 px-5 pt-10 sm:px-8 sm:pt-12 lg:min-h-[clamp(24rem,calc(100svh_-_23rem),31rem)] lg:grid-cols-[minmax(0,1fr)_minmax(0,19rem)] lg:items-end lg:gap-10 lg:pt-0">
        <div className="self-center lg:py-10">
          <HeroCopy />
        </div>
        {/* The source art is 721px wide, so it stays at or under ~360px to remain sharp on 2x screens. */}
        <Image
          src="/illustrations/gco-characters.png"
          alt=""
          width={721}
          height={339}
          sizes="(min-width: 1024px) 304px, (min-width: 640px) 272px, 240px"
          className="mx-auto w-full max-w-[15rem] sm:max-w-[17rem] lg:mx-0 lg:max-w-none"
        />
      </div>
    </section>
  );
}
