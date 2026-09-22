import Image from "next/image";
import Link from "next/link";

import { PublicAccountAction } from "@/features/public/components/public-account-action";

export function HomepageHero() {
  return (
    <section className="relative overflow-hidden bg-[var(--compass-brand-maroon-strong)] text-white">
      <Image
        src="/brand/campus-bg.jpg"
        alt=""
        fill
        sizes="100vw"
        className="object-cover opacity-25"
        priority
        aria-hidden="true"
      />
      <div className="absolute inset-0 bg-gradient-to-r from-[var(--compass-brand-maroon-strong)] via-[var(--compass-brand-maroon)]/90 to-[var(--compass-support-strong)]/65" />

      <div className="relative mx-auto grid min-h-[34rem] w-full max-w-7xl items-end gap-8 px-5 py-12 sm:px-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-16">
        <div className="z-10 max-w-2xl space-y-6">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-white/75">
            Guidance and Counseling Office
          </p>
          <div className="space-y-4">
            <h1 className="font-heading text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl">
              Guidance for the path ahead.
            </h1>
            <p className="max-w-xl text-base leading-7 text-white/85 sm:text-lg">
              Find Guidance and Counseling Office announcements, resources, and a clear way into
              COMPASS when you need university support.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <PublicAccountAction className="bg-white text-[var(--compass-brand-maroon-strong)] hover:bg-white/90" />
            <Link
              href="/services"
              className="inline-flex min-h-10 items-center justify-center rounded-lg border border-white/50 px-4 py-2 text-sm font-semibold text-white no-underline hover:bg-white/10"
            >
              Explore support
            </Link>
          </div>
        </div>

        <div className="relative mx-auto h-64 w-full max-w-xl sm:h-80 lg:h-[25rem]" aria-hidden="true">
          <Image
            src="/illustrations/gco-characters.png"
            alt=""
            fill
            sizes="(min-width: 1024px) 45vw, 90vw"
            className="object-contain object-bottom"
            priority
          />
        </div>
      </div>
    </section>
  );
}
