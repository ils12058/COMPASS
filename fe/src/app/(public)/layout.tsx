import type { Metadata } from "next";
import type { ReactNode } from "react";

import { PublicSiteFooter } from "@/features/public/components/public-site-footer";
import { PublicSiteHeader } from "@/features/public/components/public-site-header";

export const metadata: Metadata = {
  title: {
    default: "COMPASS | Guidance and Counseling Office",
    template: "%s | COMPASS",
  },
  description:
    "Public information, announcements, and Guidance and Counseling Office resources from the University of Camarines Norte.",
  openGraph: {
    title: "COMPASS | Guidance and Counseling Office",
    description:
      "Public information, announcements, and Guidance and Counseling Office resources from the University of Camarines Norte.",
    images: [
      {
        url: "/brand/compass-open-graph.jpg",
        alt: "COMPASS — University of Camarines Norte",
      },
    ],
  },
};

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <a
        href="#main-content"
        className="fixed left-4 top-4 z-[60] -translate-y-24 rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground no-underline focus:translate-y-0"
      >
        Skip to content
      </a>
      <PublicSiteHeader />
      <main id="main-content">{children}</main>
      <PublicSiteFooter />
    </>
  );
}
