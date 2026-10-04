export type InitialPushState = "unsupported" | "install-required" | "blocked" | "available";

export function initialPushState(options: {
  appleMobile: boolean;
  standalone: boolean;
  supported: boolean;
  permission: NotificationPermission;
}): InitialPushState {
  if (options.appleMobile && !options.standalone) return "install-required";
  if (!options.supported) return "unsupported";
  if (options.permission === "denied") return "blocked";
  return "available";
}
