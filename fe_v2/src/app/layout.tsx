import type { Metadata } from "next";
import { Caveat, Outfit, Plus_Jakarta_Sans, Geist } from "next/font/google";
import type { ReactNode } from "react";

import { Providers } from "@/app/providers";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getInitialPlatformStatus } from "@/lib/server/service-status";

import "@/styles/globals.css";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

const plusJakarta = Plus_Jakarta_Sans({
  display: "swap",
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const outfit = Outfit({
  display: "swap",
  variable: "--font-outfit",
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
});

const caveat = Caveat({
  display: "swap",
  variable: "--font-caveat",
  subsets: ["latin"],
  weight: ["500", "600"],
});

export const metadata: Metadata = {
  title: "COMPASS",
  description:
    "Guidance and Counseling Office updates, services, and resources for the University of Camarines Norte community.",
  applicationName: "COMPASS",
  icons: {
    icon: "/brand/compass-mark.svg",
  },
  openGraph: {
    title: "COMPASS",
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

export default async function RootLayout({ children }: { children: ReactNode }) {
  const initialPlatformStatus = await getInitialPlatformStatus();

  return (
    <html
      lang="en"
      className={cn("h-full", "antialiased", plusJakarta.variable, outfit.variable, caveat.variable, "font-sans", geist.variable)}
    >
      <body className="min-h-full bg-background text-foreground">
        <TooltipProvider>
          <Providers initialPlatformStatus={initialPlatformStatus}>{children}</Providers>
        </TooltipProvider>
      </body>
    </html>
  );
}
