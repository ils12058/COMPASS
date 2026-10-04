import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "COMPASS — UCN Guidance and Counseling Office",
    short_name: "COMPASS",
    description: "Guidance and Counseling Office services at the University of Camarines Norte.",
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#fff7ed",
    theme_color: "#7f1d1d",
    icons: [
      { src: "/brand/compass-192.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/compass-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
