import Image from "next/image";
import Link from "next/link";

export function PortalNavigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col bg-brand-strong text-on-brand">
      <Link
        href="/portal"
        onClick={onNavigate}
        className="flex min-h-18 items-center gap-3 border-b border-on-brand/15 px-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand"
        aria-label="COMPASS portal home"
      >
        <Image src="/brand/compass-mark.svg" width={36} height={36} alt="" aria-hidden="true" />
        <span className="font-heading text-lg font-bold tracking-[0.08em]">COMPASS</span>
      </Link>
      <nav aria-label="Portal navigation" className="p-3">
        <Link
          href="/portal"
          onClick={onNavigate}
          aria-current="page"
          className="flex min-h-11 items-center rounded-md bg-on-brand/12 px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand"
        >
          Home
        </Link>
      </nav>
    </div>
  );
}
