export const GUIDE_STORAGE_KEY = "compass.portal-orientation";
export const GUIDE_VERSION = 1;
export type GuidePreference = "new" | "dismissed" | "completed";

export function parseGuidePreference(raw: string | null, version = GUIDE_VERSION): GuidePreference {
  try {
    const value: unknown = raw ? JSON.parse(raw) : null;
    if (!value || typeof value !== "object" || !("version" in value) || value.version !== version || !("status" in value)) return "new";
    return value.status === "completed" || value.status === "dismissed" ? value.status : "new";
  } catch { return "new"; }
}

export function readTaskPreference(id: string, version: number): GuidePreference {
  try { return parseGuidePreference(window.localStorage.getItem(`compass.task-guide.${id}`), version); }
  catch { return "new"; }
}

export function saveTaskPreference(id: string, version: number, status: Exclude<GuidePreference, "new">) {
  try { window.localStorage.setItem(`compass.task-guide.${id}`, JSON.stringify({ version, status })); }
  catch { /* A guide works without persistence. */ }
}

export function readGuidePreference(): GuidePreference {
  try { return parseGuidePreference(window.localStorage.getItem(GUIDE_STORAGE_KEY)); }
  catch { return "new"; }
}

export function saveGuidePreference(status: Exclude<GuidePreference, "new">) {
  try { window.localStorage.setItem(GUIDE_STORAGE_KEY, JSON.stringify({ version: GUIDE_VERSION, status })); }
  catch { /* The guide remains usable when browser storage is unavailable. */ }
}
