// Browser regressions may replace external providers only on the local test server. The public
// flag is baked into a separate test build; it never enables a seam on a deployed host.
export function isLoopbackHostname(hostname: string): boolean {
  return hostname === "localhost" || hostname === "[::1]" || hostname === "::1" ||
    /^127(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}$/.test(hostname);
}

export function browserTestRuntimeEnabled(): boolean {
  return (
    (process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE === "1") &&
    typeof window !== "undefined" &&
    isLoopbackHostname(window.location.hostname)
  );
}
