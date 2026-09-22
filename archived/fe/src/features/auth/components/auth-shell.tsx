import Image from "next/image";
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
    <main className="min-h-screen px-5 py-10 sm:px-8">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] w-full max-w-5xl items-center gap-8 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="relative overflow-hidden rounded-2xl border bg-[var(--compass-brand-maroon)] p-7 text-white shadow-md sm:p-9 lg:min-h-[34rem]">
          <Image
            src="/brand/campus-bg.jpg"
            alt=""
            fill
            sizes="(min-width: 1024px) 45vw, 100vw"
            className="object-cover opacity-25"
            priority
            aria-hidden="true"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-[var(--compass-brand-maroon-strong)]/95 via-[var(--compass-brand-maroon)]/80 to-[var(--compass-support-strong)]/70" />

          <div className="relative flex h-full flex-col justify-between gap-12">
            <div className="flex items-center gap-3">
              <Image
                src="/brand/ucn-logo.png"
                alt=""
                width={49}
                height={45}
                priority
                aria-hidden="true"
              />
              <span className="h-8 w-px bg-white/35" aria-hidden="true" />
              <Image
                src="/brand/compass-mark.svg"
                alt=""
                width={46}
                height={46}
                unoptimized
                priority
                aria-hidden="true"
              />
            </div>

            <div className="space-y-3">
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-white/80">
                University of Camarines Norte
              </p>
              <p className="font-heading text-3xl font-bold tracking-tight">COMPASS</p>
              <p className="max-w-md text-sm leading-6 text-white/80">
                Counseling Office Management Platform and Student Services
              </p>
            </div>
          </div>
        </section>

        <section className="rounded-xl border bg-card p-6 shadow-md sm:p-8">
          <div className="mb-6 space-y-2">
            <h1 className="font-heading text-3xl font-bold tracking-tight">{title}</h1>
            <p className="text-muted-foreground">{description}</p>
          </div>
          {children}
        </section>
      </div>
    </main>
  );
}
