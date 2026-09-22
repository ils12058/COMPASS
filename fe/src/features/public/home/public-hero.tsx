import { ArrowRight } from "lucide-react";
import Link from "next/link";

export function PublicHero() {
  return (
    <section className="public-hero relative isolate overflow-hidden text-on-brand">
      <div className="public-hero-campus absolute inset-y-0 right-0 -z-10 w-full sm:w-[66%]" aria-hidden="true" />
      <div className="absolute inset-0 -z-20 bg-brand-strong/10" aria-hidden="true" />
      <div className="mx-auto flex min-h-[31rem] max-w-6xl items-center px-5 py-16 sm:px-8 sm:py-20 lg:min-h-[35rem]">
        <div className="max-w-2xl">
          <p className="font-heading text-sm font-bold tracking-[0.2em] text-on-brand/80">COMPASS</p>
          <h1 className="mt-4 font-heading text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
            Counseling Office Management Platform and Student Services
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-on-brand/85 sm:text-lg">
            The online platform of the UCN Guidance and Counseling Office.
          </p>
          <Link
            href="/login"
            className="mt-8 inline-flex min-h-11 items-center gap-2 rounded-md border border-on-brand bg-on-brand px-5 py-2.5 text-sm font-bold text-brand-strong transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand focus-visible:ring-offset-2 focus-visible:ring-offset-brand-strong"
          >
            Sign in to COMPASS
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
}
