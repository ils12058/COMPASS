import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

export function AuthShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-[var(--compass-body)] px-4 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] w-full max-w-6xl items-stretch gap-4 sm:min-h-[calc(100vh-3rem)] lg:min-h-[calc(100vh-4rem)] lg:grid-cols-[0.88fr_1.12fr] lg:gap-6">
        <section className="relative isolate min-h-[18rem] overflow-hidden rounded-[1.75rem] border border-[color-mix(in_srgb,var(--compass-brand-maroon)_55%,transparent)] bg-[var(--compass-brand-maroon)] p-7 text-white shadow-[var(--compass-shadow-md)] sm:p-9 lg:min-h-full lg:p-10">
          <Image
            src="/brand/campus-bg.jpg"
            alt=""
            fill
            sizes="(min-width: 1024px) 42vw, 100vw"
            className="-z-20 object-cover opacity-25"
            priority
            aria-hidden="true"
          />
          <div className="absolute inset-0 -z-10 bg-gradient-to-br from-[var(--compass-brand-maroon-strong)]/95 via-[var(--compass-brand-maroon)]/85 to-[var(--compass-support-strong)]/75" />
          <div className="absolute -right-12 -bottom-8 -z-10 h-64 w-64 rounded-full bg-[var(--compass-brand-gold)]/20 blur-3xl" />

          <div className="relative flex h-full flex-col justify-between gap-12">
            <div className="flex items-center gap-3">
              <Image
                src="/brand/ucn-logo.png"
                alt=""
                width={50}
                height={46}
                priority
                aria-hidden="true"
              />
              <span className="h-9 w-px bg-white/35" aria-hidden="true" />
              <Image
                src="/brand/compass-mark.svg"
                alt=""
                width={48}
                height={48}
                unoptimized
                priority
                aria-hidden="true"
              />
              <span className="font-heading text-xl font-bold tracking-[0.18em]">
                COMPASS
              </span>
            </div>

            <div className="max-w-md space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/75">
                University of Camarines Norte
              </p>
              <h2 className="max-w-sm font-heading text-4xl font-bold leading-[1.05] tracking-tight text-white sm:text-5xl">
                Support for your next step.
              </h2>
              <p className="max-w-sm text-sm leading-7 text-white/80 sm:text-base">
                Guidance and counseling services for UCNians.
              </p>
            </div>
          </div>
        </section>

        <section className="flex items-center justify-center rounded-[1.75rem] border border-[var(--compass-border)] bg-[var(--compass-surface)] p-6 shadow-[var(--compass-shadow-md)] sm:p-10 lg:p-12">
          <div className="w-full max-w-xl">
            <div className="mb-7 space-y-2">
              <h1 className="font-heading text-3xl font-bold tracking-tight sm:text-4xl">
                {title}
              </h1>
              <p className="max-w-lg leading-7 text-muted-foreground">{description}</p>
            </div>
            {children}
            <p className="mt-8 text-center text-sm text-muted-foreground">
              <Link className="font-semibold text-[var(--compass-brand-maroon)]" href="/">
                Back to COMPASS
              </Link>
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
