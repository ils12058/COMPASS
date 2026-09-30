import { Caveat } from "next/font/google";

// Script accent approved for the public site only (fe/AGENTS.md, Approved typography). It is
// imported by the public route layout so authenticated routes never load it.
export const caveat = Caveat({
  variable: "--font-caveat",
  subsets: ["latin"],
  display: "swap",
});

export const publicFontVariables = caveat.variable;
