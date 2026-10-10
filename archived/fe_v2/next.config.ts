import type { NextConfig } from "next";

function getApiBaseUrl(): string | null {
  const value = process.env.COMPASS_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

const nextConfig: NextConfig = {
  async rewrites() {
    const apiBaseUrl = getApiBaseUrl();

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
