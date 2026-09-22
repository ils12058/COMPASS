const FALLBACK_PATH = "/portal";
const SAFE_ORIGIN = "https://compass.local";

export function getSafeInternalPath(
  value: string | null | undefined,
  fallback = FALLBACK_PATH,
): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }

  try {
    const parsed = new URL(value, SAFE_ORIGIN);
    if (parsed.origin !== SAFE_ORIGIN) {
      return fallback;
    }

    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}
