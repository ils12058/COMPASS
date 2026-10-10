import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

export function PublicBrand({ footer = false, compact = false }: { footer?: boolean; compact?: boolean }) {
  return (
    <Link
      href="/"
      className={cn("public-brand", footer && "public-brand--footer")}
      aria-label="COMPASS home"
    >
      <span className="public-brand__marks" aria-hidden="true">
        <Image
          className="public-brand__mark-image public-brand__mark-image--ucn"
          src="/brand/ucn-logo.png"
          alt=""
          width={compact ? 30 : 36}
          height={compact ? 28 : 33}
        />
        <span className="public-brand__divider" />
        <Image
          className="public-brand__mark-image public-brand__mark-image--compass"
          src="/brand/compass-mark.svg"
          alt=""
          width={compact ? 31 : 36}
          height={compact ? 31 : 36}
          unoptimized
        />
      </span>
      <span className="public-brand__copy">
        <span className="public-brand__product">COMPASS</span>
        <span className="public-brand__office">Guidance and Counseling Office</span>
      </span>
    </Link>
  );
}
