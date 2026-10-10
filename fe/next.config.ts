import type { NextConfig } from "next";

const apiBaseUrl = process.env.COMPASS_API_BASE_URL?.replace(/\/$/, "");

const nextConfig: NextConfig = {
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
