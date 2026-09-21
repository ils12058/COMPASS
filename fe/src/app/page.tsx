import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen px-5 py-10 sm:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-5xl items-center">
        <section className="max-w-3xl space-y-6">
          <Image
            src="/brand/compass-mark.svg"
            alt=""
            width={64}
            height={64}
            unoptimized
            priority
            aria-hidden="true"
          />

          <div className="space-y-3">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
              University of Camarines Norte
            </p>
            <h1 className="font-heading text-5xl font-bold tracking-tight sm:text-6xl">
              COMPASS
            </h1>
            <p className="max-w-2xl text-lg text-muted-foreground">
              Counseling Office Management Platform and Student Services
            </p>
          </div>

          <Link
            href="/login"
            className="inline-flex min-h-11 items-center rounded-lg bg-primary px-5 py-2 text-base font-semibold text-primary-foreground no-underline shadow-sm hover:bg-[var(--compass-brand-maroon-strong)]"
          >
            Sign in to COMPASS
          </Link>
        </section>
      </div>
    </main>
  );
}
