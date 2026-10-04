"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { initialPushState } from "@/features/notifications/browser-push-capability";
import { disableBrowserPush, enableBrowserPush } from "@/features/notifications/browser-push-actions";
import {
  notificationsGetPushConfig,
  notificationsGetPushStatus,
  notificationsRegisterPushSubscription,
  notificationsRemovePushSubscription,
} from "@/lib/api/generated/notifications/notifications";

type PushState = "loading" | "unsupported" | "install-required" | "blocked" | "available" | "enabled" | "unavailable";
type InstallEvent = Event & { prompt(): Promise<void>; userChoice: Promise<{ outcome: string }> };

function isStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

function isAppleMobile() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
}

function pushSupported() {
  return window.isSecureContext && "serviceWorker" in navigator &&
    "PushManager" in window && "Notification" in window;
}

async function readyServiceWorker(): Promise<ServiceWorkerRegistration> {
  await navigator.serviceWorker.register("/sw.js");
  let timer: number | undefined;
  try {
    return await Promise.race([
      navigator.serviceWorker.ready,
      new Promise<never>((_resolve, reject) => {
        timer = window.setTimeout(() => reject(new Error("Service worker not ready")), 10_000);
      }),
    ]);
  } finally {
    window.clearTimeout(timer);
  }
}

export function BrowserPushControls() {
  const [state, setState] = useState<PushState>("loading");
  const [publicKey, setPublicKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [installPrompt, setInstallPrompt] = useState<InstallEvent | null>(null);
  const [checkVersion, setCheckVersion] = useState(0);

  useEffect(() => {
    let active = true;
    const installed = isStandalone();
    function onInstall(event: Event) {
      event.preventDefault();
      if (active && !isStandalone()) setInstallPrompt(event as InstallEvent);
    }
    window.addEventListener("beforeinstallprompt", onInstall);
    async function load() {
      const initial = initialPushState({
        appleMobile: isAppleMobile(), standalone: installed,
        supported: pushSupported(),
        permission: "Notification" in window ? Notification.permission : "default",
      });
      if (initial !== "available") {
        setState(initial);
        return;
      }
      try {
        const config = (await notificationsGetPushConfig()).data;
        if (!active) return;
        if (!config.enabled || !config.public_key) {
          setState("unavailable");
          return;
        }
        setPublicKey(config.public_key);
        const registration = await readyServiceWorker();
        const subscription = await registration.pushManager.getSubscription();
        if (!active) return;
        if (!subscription) {
          setState("available");
          return;
        }
        const status = await notificationsGetPushStatus({ endpoint: subscription.endpoint });
        if (active) setState(status.data.enabled_on_this_device ? "enabled" : "available");
      } catch {
        if (active) setState("unavailable");
      }
    }
    void load();
    return () => { active = false; window.removeEventListener("beforeinstallprompt", onInstall); };
  }, [checkVersion]);

  async function enable() {
    setBusy(true);
    setError(null);
    try {
      const result = await enableBrowserPush({
        permission: Notification.permission,
        requestPermission: () => Notification.requestPermission(),
        registration: readyServiceWorker,
        publicKey,
        register: notificationsRegisterPushSubscription,
      });
      setState(result === "enabled" ? "enabled" : result === "blocked" ? "blocked" : "available");
    } catch {
      setError("Browser notifications could not be enabled. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true);
    setError(null);
    try {
      await disableBrowserPush({ registration: readyServiceWorker, remove: notificationsRemovePushSubscription });
      setState("available");
    } catch {
      setError("Browser notifications could not be disabled. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel aria-labelledby="preferences-notifications-heading">
      <PanelHeader title="Notifications" titleId="preferences-notifications-heading" />
      <PanelBody>
        <h3 className="font-semibold text-ink">Browser notifications</h3>
        <p className="mt-1 text-sm leading-6 text-muted">Get important COMPASS updates on this device. Your in-app notifications and email settings are separate.</p>
        {state === "loading" ? <p role="status" className="mt-3 text-sm text-muted">Checking this device…</p> : null}
        {state === "unsupported" ? <p className="mt-3 text-sm text-muted">Browser notifications are unavailable in this browser or connection.</p> : null}
        {state === "unavailable" ? <Notice tone="warning" className="mt-3">Browser notifications are currently unavailable. Your in-app notifications still work. <Button variant="secondary" className="mt-3" onClick={() => setCheckVersion((value) => value + 1)}>Check again</Button></Notice> : null}
        {state === "install-required" ? (
          <div className="mt-3 text-sm leading-6 text-muted">
            <p>Install COMPASS to receive notifications on this iPhone or iPad.</p>
            <details className="mt-2"><summary className="cursor-pointer font-semibold text-brand">How to install</summary><p className="mt-2">In Safari, tap Share, then Add to Home Screen. Open COMPASS from your Home Screen and return here.</p></details>
          </div>
        ) : null}
        {state === "blocked" ? <div className="mt-3"><p className="text-sm text-muted">Notifications are blocked in your browser or device settings. Allow them there before trying again.</p><Button variant="secondary" className="mt-3" onClick={() => setCheckVersion((value) => value + 1)}>Check again</Button></div> : null}
        {state === "available" ? <Button className="mt-4" disabled={busy} onClick={() => void enable()}>{busy ? "Enabling…" : "Enable on this device"}</Button> : null}
        {state === "enabled" ? <div className="mt-3"><p className="text-sm text-success">Enabled on this device.</p><Button className="mt-3" variant="secondary" disabled={busy} onClick={() => void disable()}>{busy ? "Disabling…" : "Disable on this device"}</Button></div> : null}
        {error ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
        {installPrompt ? <Button className="mt-4" variant="secondary" onClick={() => { void installPrompt.prompt(); setInstallPrompt(null); }}>Install COMPASS</Button> : null}
      </PanelBody>
    </Panel>
  );
}
