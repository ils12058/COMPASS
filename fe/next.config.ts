import type { NextConfig } from "next";

const apiBaseUrl = process.env.COMPASS_API_BASE_URL?.replace(/\/$/, "");

function policyOrigin(value: string, name: string, protocols: string[], originOnly = true): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${name} must contain valid origins.`);
  }
  if (
    !protocols.includes(url.protocol) || url.username || url.password || url.search || url.hash ||
    /[\s;,*]/.test(value) || (originOnly && url.pathname !== "/")
  ) {
    throw new Error(`${name} must contain origins without credentials, paths, or policy syntax.`);
  }
  return url.origin;
}

const siteOrigin = policyOrigin(
  process.env.COMPASS_SITE_URL ?? "http://localhost:3000", "COMPASS_SITE_URL", ["http:", "https:"],
);
// ObjectStorage returns deployment-specific photo and signed file URLs. The owner supplies the
// browser-facing origins, including the separate recording bucket, without exposing storage keys.
const storageOrigins = [...new Set((process.env.COMPASS_CSP_STORAGE_ORIGINS ?? "")
  .split(",").map((origin) => origin.trim()).filter(Boolean)
  .map((origin) => policyOrigin(origin, "COMPASS_CSP_STORAGE_ORIGINS", ["https:"])))];
const realtimeOrigins = process.env.NEXT_PUBLIC_REALTIME_URL ? [policyOrigin(
  process.env.NEXT_PUBLIC_REALTIME_URL.trim(), "NEXT_PUBLIC_REALTIME_URL", ["wss:", "ws:"], false,
)] : [];
// Match only the existing local realtime test seam; ordinary builds never allow these sockets.
const testSocketOrigins = process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE === "1"
  ? ["ws://localhost:*", "ws://127.0.0.1:*"] : [];

// Static pages and the accessibility bootstrap need inline scripts/styles. Nonces would require
// changing rendering/cache behavior. Keep the full policy report-only until real Turnstile,
// Daily (including its avoidEval requirement), and configured storage have been verified.
const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com https://c.daily.co https://*.daily.co",
  "style-src 'self' 'unsafe-inline'",
  ["img-src 'self' data: blob:", ...storageOrigins].join(" "),
  "font-src 'self'",
  ["connect-src 'self' blob: https://challenges.cloudflare.com https://*.daily.co wss://*.daily.co", ...realtimeOrigins, ...storageOrigins, ...testSocketOrigins].join(" "),
  ["media-src 'self' blob: https://*.daily.co", ...storageOrigins].join(" "),
  "frame-src 'self' blob: https://challenges.cloudflare.com https://*.daily.co",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");

const nextConfig: NextConfig = {
  // Bake an explicit false into ordinary builds so provider test seams are eliminated. Only the
  // separate local browser artifact opts in; runtime environment changes cannot enable it.
  env: {
    NEXT_PUBLIC_COMPASS_UI_TEST_MODE: process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE === "1" ? "1" : "0",
  },
  // Raster sources are WebP; next/image offers AVIF first and WebP otherwise, at each size.
  images: {
    formats: ["image/avif", "image/webp"],
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(self), microphone=(self), display-capture=(self), geolocation=(), payment=(), usb=()" },
        { key: "Content-Security-Policy-Report-Only", value: contentSecurityPolicy },
        // COMPASS browser/API traffic is same-origin. Override a hosting wildcard with the
        // configured canonical site origin; never reflect an incoming Origin header.
        { key: "Access-Control-Allow-Origin", value: siteOrigin },
      ],
    }, {
      source: "/account-recovery",
      headers: [
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "Cache-Control", value: "no-store" },
      ],
    }, {
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
