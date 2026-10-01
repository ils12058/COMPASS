"use client";

import Link from "next/link";
import type { ComponentProps } from "react";

import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";

type GuardedPortalLinkProps = ComponentProps<typeof Link>;

function destinationPathname(
  href: GuardedPortalLinkProps["href"],
): string | null {
  if (typeof href === "string") {
    return new URL(href, window.location.href).pathname;
  }
  return typeof href.pathname === "string"
    ? new URL(href.pathname, window.location.href).pathname
    : null;
}

export function GuardedPortalLink({
  href,
  onNavigate,
  ...props
}: GuardedPortalLinkProps) {
  const { confirmNavigation } = useUnsavedNavigation();

  return (
    <Link
      {...props}
      href={href}
      onNavigate={(event) => {
        if (!confirmNavigation(destinationPathname(href))) {
          event.preventDefault();
          return;
        }
        onNavigate?.(event);
      }}
    />
  );
}
