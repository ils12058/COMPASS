"use client";

import Link from "next/link";
import { forwardRef, type ComponentProps, type ReactNode } from "react";

import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { PUBLIC_SITE } from "@/features/public/config";

type PublicAccountLinkProps = Omit<
  ComponentProps<typeof Link>,
  "children" | "href"
> & {
  children?: ReactNode;
  signedInLabel?: string;
  signedOutLabel?: string;
};

export const PublicAccountLink = forwardRef<
  HTMLAnchorElement,
  PublicAccountLinkProps
>(function PublicAccountLink(
  {
    signedInLabel = "Open workspace",
    signedOutLabel = PUBLIC_SITE.accountLabel,
    children,
    ...props
  },
  ref,
) {
  const sessionQuery = useAuthGetSession({
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const isAuthenticated = sessionQuery.data?.data.authenticated === true;

  return (
    <Link ref={ref} href={isAuthenticated ? "/portal" : "/login"} {...props}>
      {isAuthenticated ? signedInLabel : signedOutLabel}
      {children}
    </Link>
  );
});

PublicAccountLink.displayName = "PublicAccountLink";
