import Image from "next/image";
import type { ReactNode } from "react";
import { PanelMessage } from "@/components/ui/panel";

// Only for a confirmed, non-sensitive empty result. Callers keep loading, filtered,
// unavailable and failed-refresh states separate; text stays complete without artwork.
export function IllustratedEmptyState({ src, children, action }: { src?: string; children: ReactNode; action?: ReactNode }) {
  return <PanelMessage className="@container" action={action}>
    <span className="flex items-center gap-4">
      {src ? <Image src={src} width={512} height={512} sizes="64px" alt="" aria-hidden="true"
        className="hidden size-16 shrink-0 @min-[14rem]:block" /> : null}
      <span className="min-w-0">{children}</span>
    </span>
  </PanelMessage>;
}
