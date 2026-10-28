import { Caveat } from "next/font/google";

// The existing public-hero script face is also used for the selected Student Overview greeting.
export const caveat = Caveat({
  variable: "--font-caveat",
  subsets: ["latin"],
  display: "swap",
});

export const scriptFontVariable = caveat.variable;
