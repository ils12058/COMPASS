import Link from "next/link";

import { PublicBrand } from "@/features/public/components/public-brand";
import { PUBLIC_NAVIGATION, PUBLIC_SITE } from "@/features/public/config";

export function PublicSiteFooter() {
  return (
    <footer className="border-t bg-[var(--compass-surface-subtle)]">
      <div className="mx-auto grid w-full max-w-7xl gap-8 px-5 py-10 sm:px-8 md:grid-cols-[1fr_auto]">
        <div className="space-y-4">
          <PublicBrand />
          <p className="max-w-md text-sm text-muted-foreground">
            {PUBLIC_SITE.office}, {PUBLIC_SITE.institution}.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <nav className="grid content-start gap-2 text-sm" aria-label="Footer navigation">
            {PUBLIC_NAVIGATION.slice(1).map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
          </nav>
          <nav className="grid content-start gap-2 text-sm" aria-label="Account and privacy">
            <Link href="/privacy">Privacy</Link>
            <Link href="/login">Sign in to COMPASS</Link>
          </nav>
        </div>
      </div>
      <div className="border-t px-5 py-4 text-center text-xs text-muted-foreground">
        {PUBLIC_SITE.product} · {PUBLIC_SITE.institution}
      </div>
    </footer>
  );
}
