import {
  notificationsRegisterPushSubscription,
  notificationsRemovePushSubscription,
} from "@/lib/api/generated/notifications/notifications";

export function applicationServerKey(encoded: string): Uint8Array<ArrayBuffer> {
  const base64 = (encoded + "=".repeat((4 - encoded.length % 4) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

type PushActions = {
  permission: NotificationPermission;
  requestPermission: () => Promise<NotificationPermission>;
  registration: () => Promise<ServiceWorkerRegistration>;
  publicKey: string;
  register: typeof notificationsRegisterPushSubscription;
  remove: typeof notificationsRemovePushSubscription;
};

export async function enableBrowserPush(actions: Pick<PushActions, "permission" | "requestPermission" | "registration" | "publicKey" | "register">) {
  if (actions.permission === "denied") return "blocked" as const;
  const permission = actions.permission === "granted" ? "granted" : await actions.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "blocked" as const : "dismissed" as const;
  const registration = await actions.registration();
  let subscription = await registration.pushManager.getSubscription();
  let created = false;
  try {
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true, applicationServerKey: applicationServerKey(actions.publicKey),
      });
      created = true;
    }
    const keys = subscription.toJSON().keys;
    if (!keys?.p256dh || !keys.auth) throw new Error("Missing browser subscription keys");
    await actions.register({ endpoint: subscription.endpoint, keys: { p256dh: keys.p256dh, auth: keys.auth } });
    return "enabled" as const;
  } catch (error) {
    if (created && subscription) await subscription.unsubscribe().catch(() => undefined);
    throw error;
  }
}

export async function disableBrowserPush(actions: Pick<PushActions, "registration" | "remove">) {
  const registration = await actions.registration();
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    await actions.remove({ endpoint: subscription.endpoint });
    await subscription.unsubscribe();
  }
}
