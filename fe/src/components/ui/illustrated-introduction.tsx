import Image from "next/image";
import type { ReactNode } from "react";

// An accent beside an existing introduction, without another card, heading or action.
// Feature owners decide whether this is a safe introduction or an unavailable/private state.
export function IllustratedIntroduction({ src, children }: { src?: string; children: ReactNode }) {
  return <div className="@container">
    <div className="flex items-center gap-4">
      <div className="min-w-0 flex-1">{children}</div>
      {src ? <Image src={src} width={512} height={512} sizes="112px" alt="" aria-hidden="true"
        className="hidden size-20 shrink-0 @min-[18rem]:block @min-[32rem]:size-28" /> : null}
    </div>
  </div>;
}
