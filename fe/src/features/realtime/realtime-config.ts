// Realtime is a dark-launched acceleration layer (ADR-100): it is off unless this build enables it
// and names the realtime WebSocket URL, and nothing in COMPASS depends on it being on.
//
// The socket connects directly to the API host's realtime route. It never relies on cookies:
// a one-time ticket from the ordinary same-origin HTTP API authenticates it.

import { browserTestRuntimeEnabled, isLoopbackHostname } from "@/lib/browser-test-runtime";

export const REALTIME_SOCKET_PATH = "/api/realtime/v1/socket";

export type RealtimeConfig = { enabled: false } | { enabled: true; url: string };

declare global {
  interface Window {
    // Local browser regressions only, including explicitly flagged production test builds.
    // Ordinary production builds drop the code that reads it.
    __COMPASS_REALTIME_TEST_CONFIG__?: { url: string };
  }
}

const DISABLED: RealtimeConfig = { enabled: false };

/** Accepts only the exact realtime socket URL: wss (ws outside production), no query or fragment. */
export function parseRealtimeConfig(
  enabled: string | undefined,
  url: string | undefined,
  { production }: { production: boolean },
): RealtimeConfig {
  if (enabled?.trim() !== "true" || !url) return DISABLED;
  let parsed: URL;
  try {
    parsed = new URL(url.trim());
  } catch {
    return DISABLED;
  }
  const schemes = production ? ["wss:"] : ["wss:", "ws:"];
  if (
    !schemes.includes(parsed.protocol) ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    url.includes("?") ||
    url.includes("#") ||
    parsed.pathname !== REALTIME_SOCKET_PATH
  ) {
    return DISABLED;
  }
  return { enabled: true, url: parsed.href };
}

export function realtimeConfig(): RealtimeConfig {
  const production = process.env.NODE_ENV === "production";
  // Keep the literal build guard here so ordinary production drops even the window seam read.
  if ((process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE === "1") && browserTestRuntimeEnabled() && window.__COMPASS_REALTIME_TEST_CONFIG__) {
    const testConfig = parseRealtimeConfig("true", window.__COMPASS_REALTIME_TEST_CONFIG__.url, { production: false });
    return testConfig.enabled && isLoopbackHostname(new URL(testConfig.url).hostname)
      ? testConfig
      : DISABLED;
  }
  // Next inlines NEXT_PUBLIC_* values at build time, so they must be read literally.
  return parseRealtimeConfig(
    process.env.NEXT_PUBLIC_REALTIME_ENABLED,
    process.env.NEXT_PUBLIC_REALTIME_URL,
    { production },
  );
}
