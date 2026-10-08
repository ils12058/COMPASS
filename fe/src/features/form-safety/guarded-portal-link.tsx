"use client";

import Link from "next/link";
import type { ComponentProps } from "react";

import { useOptionalActiveECounselingCall } from "@/features/ecounseling/runtime/active-call-context";
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
  const call = useOptionalActiveECounselingCall();

  return (
    <Link
      {...props}
      href={href}
      onNavigate={(event) => {
        const destination = destinationPathname(href);
        if (!confirmNavigation(destination)) {
          event.preventDefault();
          return;
        }
        // Portal pages keep a live E-Counseling call (ADR-094); only leaving the portal ends it.
        // This is separate from unsaved changes, which keep their own question above.
        const leavesPortal = destination !== null && destination !== "/portal" && !destination.startsWith("/portal/");
        if (call?.live && leavesPortal && !window.confirm("Leaving the portal will end your E-Counseling call.")) {
          event.preventDefault();
          return;
        }
        onNavigate?.(event);
      }}
    />
  );
}
