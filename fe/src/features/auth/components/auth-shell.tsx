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
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] w-full max-w-5xl items-center gap-10 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="space-y-5">
          <Image
            src="/brand/compass-mark.svg"
            alt=""
            width={56}
            height={56}
            unoptimized
            priority
            aria-hidden="true"
          />
          <div className="space-y-2">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
              University of Camarines Norte
            </p>
            <h1 className="font-heading text-4xl font-bold tracking-tight">{title}</h1>
            <p className="max-w-xl text-muted-foreground">{description}</p>
          </div>
        </section>

        <section className="rounded-xl border bg-card p-6 shadow-md sm:p-8">
          {children}
        </section>
      </div>
    </main>
  );
}
