import Image from "next/image";
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl items-center px-6 py-12">
      <section className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <Image
          src="/illustrations/gco-character-point-up.png"
          width={330}
          height={330}
          alt=""
          aria-hidden="true"
          priority
          className="h-28 w-auto shrink-0 self-start sm:h-36 sm:self-auto"
        />
        <div>
          <h1 className="font-heading text-3xl font-bold text-ink">Page not found</h1>
          <p className="mt-3 leading-7 text-muted">
            The requested page does not exist or is no longer available.
          </p>
          <Link
            href="/"
            className="mt-6 inline-flex min-h-10 items-center rounded-md text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Return to COMPASS
          </Link>
        </div>
      </section>
    </main>
  );
}
