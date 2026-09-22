import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export function ArrowLink({
  href,
  children,
  className = "",
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link href={href} className={`landing-content-link ${className}`.trim()}>
      {children}
      <ArrowUpRight aria-hidden="true" />
    </Link>
  );
}

export function PaperSheet({
  children,
  className = "",
  tone = "plain",
}: {
  children: ReactNode;
  className?: string;
  tone?: "paper" | "plain" | "sage";
}) {
  return (
    <article className={`landing-paper-sheet ${className}`.trim()} data-tone={tone}>
      {children}
    </article>
  );
}

export function StickyNote({
  children,
  tone,
  rotation,
}: {
  children: ReactNode;
  tone: "butter" | "sage" | "rose";
  rotation: "left" | "right";
}) {
  return (
    <article className="landing-sticky-note" data-tone={tone} data-rotation={rotation}>
      <span className="landing-sticky-note__tape" aria-hidden="true" />
      {children}
    </article>
  );
}
