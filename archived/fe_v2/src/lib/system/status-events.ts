export const COMPASS_MAINTENANCE_SIGNAL_EVENT =
  "compass:maintenance-status-refresh";

export function emitMaintenanceStatusRefresh(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new Event(COMPASS_MAINTENANCE_SIGNAL_EVENT));
}
