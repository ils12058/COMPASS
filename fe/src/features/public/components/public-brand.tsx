import Image from "next/image";
import Link from "next/link";

import { PUBLIC_SITE } from "@/features/public/config";
import { cn } from "@/lib/utils/cn";

export function PublicBrand({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      href="/"
      className="flex items-center gap-2.5 no-underline"
      aria-label="COMPASS home"
    >
      <span className="flex items-center gap-2" aria-hidden="true">
        <Image
          src="/brand/ucn-logo.png"
          alt=""
          width={compact ? 30 : 36}
          height={compact ? 28 : 33}
        />
        <span className="h-7 w-px bg-border" />
        <Image
          src="/brand/compass-mark.svg"
          alt=""
          width={compact ? 31 : 36}
          height={compact ? 31 : 36}
          unoptimized
        />
      </span>
      <span className={cn("min-w-0", compact && "hidden sm:block")}>
        <span className="block font-heading text-base font-bold leading-tight text-foreground">
          {PUBLIC_SITE.product}
        </span>
        <span className="block truncate text-[0.68rem] leading-tight text-muted-foreground">
          {PUBLIC_SITE.office}
        </span>
      </span>
    </Link>
  );
}
