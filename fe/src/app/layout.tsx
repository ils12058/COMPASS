import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/app/providers";
import { ACCESSIBILITY_BOOTSTRAP_SCRIPT } from "@/features/accessibility/accessibility-preferences";
import { fontVariables } from "@/styles/fonts";
import "@/styles/globals.css";

const shouldPreventIndexing =
  process.env.COMPASS_SITE_URL === "https://staging.compass-gco.com" ||
  process.env.VERCEL_ENV === "preview";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.COMPASS_SITE_URL ?? "http://localhost:3000"),
  title: {
    default: "COMPASS | UCN Guidance and Counseling Office",
    template: "%s | COMPASS",
  },
  description:
    "Counseling Office Management Platform and Student Services of the University of Camarines Norte Guidance and Counseling Office.",
  robots: shouldPreventIndexing
    ? { index: false, follow: false, noarchive: true, nosnippet: true }
    : undefined,
  icons: {
    icon: "/brand/compass-mark.svg",
  },
  openGraph: {
    type: "website",
    siteName: "COMPASS",
    title: "COMPASS | UCN Guidance and Counseling Office",
    description:
      "The online platform of the UCN Guidance and Counseling Office.",
    images: [
      {
        url: "/brand/compass-open-graph.jpg",
        width: 1200,
        height: 630,
        alt: "COMPASS — UCN Guidance and Counseling Office",
      },
    ],
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    // The bootstrap script applies saved accessibility settings to <html> before the first paint;
    // suppressHydrationWarning lets React accept those attributes.
    <html lang="en" className={fontVariables} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: ACCESSIBILITY_BOOTSTRAP_SCRIPT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
