import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded bg-surface-muted motion-reduce:animate-none",
        className,
      )}
      {...props}
    />
  );
}
