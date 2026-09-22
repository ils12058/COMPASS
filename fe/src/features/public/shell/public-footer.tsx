import Link from "next/link";

export function PublicFooter() {
  return (
    <footer className="bg-brand-strong text-on-brand">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-12 sm:px-8 md:grid-cols-[1.4fr_1fr_auto]">
        <div>
          <p className="font-heading text-xl font-bold tracking-[0.08em]">COMPASS</p>
          <p className="mt-3 max-w-sm text-sm leading-6 text-on-brand/80">
            Counseling Office Management Platform and Student Services
          </p>
        </div>
        <div className="text-sm leading-6 text-on-brand/80">
          <p className="font-semibold text-on-brand">University of Camarines Norte</p>
          <p>Guidance and Counseling Office</p>
        </div>
        <nav aria-label="Footer navigation" className="flex flex-col items-start gap-1 text-sm">
          <Link className="min-h-9 py-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand" href="/announcements">
            Announcements
          </Link>
          <Link className="min-h-9 py-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand" href="/resources">
            Resources
          </Link>
          <Link className="min-h-9 py-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand" href="/login">
            Sign in
          </Link>
        </nav>
      </div>
      <div className="border-t border-on-brand/20">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-5 text-xs text-on-brand/70 sm:px-8 md:flex-row md:items-center md:justify-between">
          <p>© 2026 University of Camarines Norte</p>
          <p>Developed for the UCN Guidance and Counseling Office</p>
        </div>
      </div>
    </footer>
  );
}
