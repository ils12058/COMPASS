import Image from "next/image";
import type { ReactNode } from "react";

// Feature owners decide whether an introduction is safe for decorative artwork.
export function IllustratedIntroduction({ src, children, edgeFade = false }: { src?: string; children: ReactNode; edgeFade?: boolean }) {
  if (edgeFade) return <div className="@container">
    <div className={src ? "relative @min-[40rem]:min-h-36" : "relative"}>
      {src ? <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-0 hidden w-56 overflow-hidden [mask-image:radial-gradient(ellipse_at_center,black_25%,transparent_75%)] @min-[40rem]:block">
        <Image src={src} width={512} height={512} sizes="288px" alt="" className="absolute right-[-4rem] top-1/2 size-72 max-w-none -translate-y-1/2 opacity-45" />
      </span> : null}
      <div className={src ? "relative @min-[40rem]:pr-56" : "relative"}>{children}</div>
    </div>
  </div>;
  return <div className="@container">
    <div className="flex items-center gap-4">
      <div className="min-w-0 flex-1">{children}</div>
      {src ? <Image src={src} width={512} height={512} sizes="112px" alt="" aria-hidden="true"
        className="hidden size-20 shrink-0 @min-[18rem]:block @min-[32rem]:size-28" /> : null}
    </div>
  </div>;
}
