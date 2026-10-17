import localFont from "next/font/local";

export const plusJakarta = localFont({
  src: "./fonts/plus-jakarta-sans.ttf",
  variable: "--font-plus-jakarta",
  weight: "400 700",
  display: "swap",
});

export const outfit = localFont({
  src: "./fonts/outfit.ttf",
  variable: "--font-outfit",
  weight: "500 800",
  display: "swap",
});

export const fontVariables = `${plusJakarta.variable} ${outfit.variable}`;
