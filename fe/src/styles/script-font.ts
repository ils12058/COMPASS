import { Caveat } from "next/font/google";

// The public-hero script face is also used for the Home greeting of every role.
export const caveat = Caveat({
  variable: "--font-caveat",
  subsets: ["latin"],
  display: "swap",
});

export const scriptFontVariable = caveat.variable;
