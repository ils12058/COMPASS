import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Services",
};

export default function ServicesPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
      <header className="max-w-3xl space-y-3">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">
          Guidance and Counseling Office
        </p>
        <h1 className="font-heading text-4xl font-bold tracking-tight">Services</h1>
        <p className="text-lg leading-8 text-muted-foreground">
          COMPASS provides a digital entry point to Guidance and Counseling Office services.
          Available options can depend on your signed-in account and the service configuration in
          COMPASS.
        </p>
      </header>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border bg-card p-6 shadow-sm">
          <h2 className="font-heading text-xl font-bold">Guidance support</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Sign in to view guidance-related services and actions currently available to your
            account.
          </p>
        </article>
        <article className="rounded-xl border bg-card p-6 shadow-sm">
          <h2 className="font-heading text-xl font-bold">Office updates</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Public announcements keep university visitors informed without requiring a COMPASS
            account.
          </p>
        </article>
        <article className="rounded-xl border bg-card p-6 shadow-sm">
          <h2 className="font-heading text-xl font-bold">Guidance resources</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Browse public articles, external references, and downloadable PDF resources selected
            by the office.
          </p>
        </article>
      </div>

      <div className="mt-8 rounded-xl bg-[var(--compass-support-soft)] p-6">
        <h2 className="font-heading text-2xl font-bold">Ready to continue?</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/80">
          Sign in to COMPASS to see the current service options connected to your account.
        </p>
        <Link
          href="/login"
          className="mt-4 inline-flex min-h-10 items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground no-underline"
        >
          Sign in to COMPASS
        </Link>
      </div>
    </div>
  );
}
