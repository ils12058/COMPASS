import Image from "next/image";
import Link from "next/link";

import { PUBLIC_SITE } from "@/features/public/config";

export function OfficeContactSection() {
  return (
    <section className="mx-auto grid w-full max-w-7xl items-center gap-8 px-5 py-12 sm:px-8 lg:grid-cols-[1fr_0.35fr]">
      <div className="rounded-2xl border bg-[var(--compass-support-soft)] p-7 sm:p-9">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">{PUBLIC_SITE.office}</p>
        <h2 className="mt-2 font-heading text-3xl font-bold">Need a way into COMPASS?</h2>
        <p className="mt-3 max-w-2xl leading-7 text-foreground/80">
          Sign in for account-specific services and options. For public contact guidance, visit the
          contact page; this site does not publish unverified office hours, phone numbers, or email
          addresses.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            href="/login"
            className="inline-flex min-h-10 items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground no-underline"
          >
            Sign in to COMPASS
          </Link>
          <Link href="/contact" className="inline-flex min-h-10 items-center px-1 text-sm font-semibold">
            Contact guidance
          </Link>
        </div>
      </div>

      <div className="relative mx-auto hidden h-56 w-full max-w-xs sm:block" aria-hidden="true">
        <Image
          src="/illustrations/gco-character-wave.png"
          alt=""
          fill
          sizes="25vw"
          className="object-contain object-bottom"
        />
      </div>
    </section>
  );
}
