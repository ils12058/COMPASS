import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

export function SystemErrorPage({
  code,
  title,
  description,
  primaryAction,
  secondaryHref = "/",
  secondaryLabel = "Back to COMPASS",
  requestReference,
}: {
  code: string;
  title: string;
  description: string;
  primaryAction?: ReactNode;
  secondaryHref?: string;
  secondaryLabel?: string;
  requestReference?: string | null;
}) {
  return (
    <section className="flex min-h-[65vh] items-center px-5 py-12 sm:px-8">
      <section className="mx-auto w-full max-w-xl rounded-2xl border bg-card p-7 text-center shadow-sm sm:p-9">
        <Image
          src="/brand/compass-mark.svg"
          alt=""
          width={52}
          height={52}
          unoptimized
          className="mx-auto"
          aria-hidden="true"
        />
        <p className="mt-5 text-sm font-semibold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
          {code}
        </p>
        <h1 className="mt-2 font-heading text-3xl font-bold">{title}</h1>
        <p className="mx-auto mt-3 max-w-md leading-7 text-muted-foreground">
          {description}
        </p>

        {requestReference ? (
          <p className="mt-4 text-xs text-muted-foreground">
            Reference: <code>{requestReference}</code>
          </p>
        ) : null}

        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {primaryAction}
          <Link
            href={secondaryHref}
            className="inline-flex min-h-10 items-center rounded-lg border bg-card px-4 py-2 text-sm font-semibold text-foreground no-underline hover:bg-muted"
          >
            {secondaryLabel}
          </Link>
        </div>
      </section>
    </section>
  );
}
