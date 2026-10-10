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
    "Guidance and Counseling Office updates, services, and resources for the University of Camarines Norte community.",
  openGraph: {
    title: "COMPASS | Guidance and Counseling Office",
    description:
      "Guidance and Counseling Office updates, services, and resources for the University of Camarines Norte community.",
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
    <div className="public-site flex min-h-screen flex-col bg-background text-foreground">
      <a className="landing-skip-link" href="#main-content">
        Skip to main content
      </a>
      <PublicSiteHeader />
      <main id="main-content" className="flex-1">
        {children}
      </main>
      <PublicSiteFooter />
    </div>
  );
}
