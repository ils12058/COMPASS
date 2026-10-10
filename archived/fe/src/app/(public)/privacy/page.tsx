import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy",
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:px-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">COMPASS</p>
        <h1 className="font-heading text-4xl font-bold tracking-tight">Privacy</h1>
      </header>

      <div className="mt-8 space-y-6 rounded-xl border bg-card p-7 shadow-sm">
        <section>
          <h2 className="font-heading text-2xl font-bold">Public pages</h2>
          <p className="mt-3 leading-7 text-muted-foreground">
            This public site provides Guidance and Counseling Office information, public
            announcements, and public resources. Account-specific records and services require
            sign-in through COMPASS.
          </p>
        </section>
        <section>
          <h2 className="font-heading text-2xl font-bold">Institutional privacy guidance</h2>
          <p className="mt-3 leading-7 text-muted-foreground">
            Official University of Camarines Norte privacy documentation and applicable
            institutional policies govern the university&apos;s handling of personal information.
            This page is a short orientation to the public COMPASS site, not a replacement for
            those official documents.
          </p>
        </section>
      </div>
    </div>
  );
}
