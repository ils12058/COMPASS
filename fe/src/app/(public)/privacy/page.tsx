import type { Metadata } from "next";

import { PublicPrivacyNotices } from "@/features/public/privacy/public-privacy-notices";
import { PublicPageHeader } from "@/features/public/shared/public-page-header";

export const metadata: Metadata = { title: "Privacy" };

function readPage(value: string | string[] | undefined): number {
  const parsed = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export default async function PrivacyPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string | string[] }>;
}) {
  const { page } = await searchParams;

  return (
    <main>
      <PublicPageHeader>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">Privacy</h1>
        <p className="mt-2 max-w-2xl text-base leading-7 text-muted">
          Official privacy notices for COMPASS.
        </p>
      </PublicPageHeader>
      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8 sm:py-9">
        <div className="max-w-4xl">
          <PublicPrivacyNotices page={readPage(page)} />
        </div>
      </div>
    </main>
  );
}
