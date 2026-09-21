import Link from "next/link";
import type { Metadata } from "next";

import { PUBLIC_SITE } from "@/features/public/config";

export const metadata: Metadata = {
  title: "Contact",
};

export default function ContactPage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:px-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">
          {PUBLIC_SITE.institution}
        </p>
        <h1 className="font-heading text-4xl font-bold tracking-tight">Contact</h1>
        <p className="max-w-2xl text-lg leading-8 text-muted-foreground">
          For guidance-related account services, use COMPASS to access the options available to
          your university account.
        </p>
      </header>

      <section className="mt-8 rounded-xl border bg-card p-7 shadow-sm">
        <h2 className="font-heading text-2xl font-bold">{PUBLIC_SITE.office}</h2>
        <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
          Public office contact details are not listed here unless they have been confirmed for
          this site. Use official University of Camarines Norte channels for institutional contact
          information.
        </p>
        <Link
          href="/login"
          className="mt-5 inline-flex min-h-10 items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground no-underline"
        >
          Sign in to COMPASS
        </Link>
      </section>
    </div>
  );
}
