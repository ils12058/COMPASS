import type { NextConfig } from "next";

const apiBaseUrl = process.env.COMPASS_API_BASE_URL?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Bake an explicit false into ordinary builds so provider test seams are eliminated. Only the
  // separate local browser artifact opts in; runtime environment changes cannot enable it.
  env: {
    NEXT_PUBLIC_COMPASS_UI_TEST_MODE: process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE === "1" ? "1" : "0",
  },
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
