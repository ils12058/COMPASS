import type { NextConfig } from "next";

const apiBaseUrl = process.env.COMPASS_API_BASE_URL?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  // The browser regression job exercises many routes in one Next dev server. Keep those
  // compiled entries alive for the duration of the job so a later shard test does not trigger a
  // cold recompile while Playwright's navigation timeout is running.
  ...(process.env.COMPASS_UI_TEST_MODE === "1"
    ? { onDemandEntries: { maxInactiveAge: 40 * 60 * 1000, pagesBufferLength: 128 } }
    : {}),
  async headers() {
    return [{
      source: "/sw.js",
      headers: [
        { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self'" },
        { key: "X-Content-Type-Options", value: "nosniff" },
      ],
    }];
  },
  async rewrites() {
    if (!apiBaseUrl) {
      return [];
    }

    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBaseUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
