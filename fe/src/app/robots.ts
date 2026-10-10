import type { MetadataRoute } from "next";

const shouldPreventIndexing =
  process.env.COMPASS_SITE_URL === "https://staging.compass-gco.com" ||
  process.env.VERCEL_ENV === "preview";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: shouldPreventIndexing
      ? { userAgent: "*", disallow: "/" }
      : {
          userAgent: "*",
          allow: "/",
          disallow: ["/portal", "/login", "/password"],
        },
  };
}
