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
        <h1 className="font-heading text-4xl font-bold tracking-tight text-ink">Privacy</h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
          Official privacy notices for COMPASS.
        </p>
      </PublicPageHeader>
      <div className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
        <PublicPrivacyNotices page={readPage(page)} />
      </div>
    </main>
  );
}
