"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";

type TurnstileOptions = {
  action: string;
  callback: (token: string) => void;
  "error-callback": () => void;
  "expired-callback": () => void;
  sitekey: string;
  theme: "light";
};

type TurnstileApi = {
  remove: (widgetId: string) => void;
  render: (container: HTMLElement, options: TurnstileOptions) => string;
  reset: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY?.trim() ?? "";

export const isTurnstileConfigured = siteKey.length > 0;

export function TurnstileWidget({
  action,
  onTokenChange,
  resetKey,
}: {
  action: "email_otp" | "login";
  onTokenChange: (token: string | null) => void;
  resetKey: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const onTokenChangeRef = useRef(onTokenChange);
  const [ready, setReady] = useState(false);
  const [widgetError, setWidgetError] = useState(false);

  useEffect(() => {
    onTokenChangeRef.current = onTokenChange;
  }, [onTokenChange]);

  useEffect(() => {
    if (!siteKey || !ready || !containerRef.current || !window.turnstile) return;

    setWidgetError(false);
    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      action,
      sitekey: siteKey,
      theme: "light",
      callback: (token) => onTokenChangeRef.current(token),
      "expired-callback": () => onTokenChangeRef.current(null),
      "error-callback": () => {
        onTokenChangeRef.current(null);
        setWidgetError(true);
      },
    });

    return () => {
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
      }
      widgetIdRef.current = null;
    };
  }, [action, ready]);

  useEffect(() => {
    if (resetKey > 0 && widgetIdRef.current && window.turnstile) {
      window.turnstile.reset(widgetIdRef.current);
      onTokenChangeRef.current(null);
      setWidgetError(false);
    }
  }, [resetKey]);

  if (!siteKey) return null;

  return (
    <div>
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        strategy="afterInteractive"
        onReady={() => setReady(true)}
        onError={() => setWidgetError(true)}
      />
      <div ref={containerRef} className="min-h-[65px] max-w-full overflow-hidden" />
      {widgetError ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          Security verification could not load. Refresh the page and try again.
        </p>
      ) : null}
    </div>
  );
}
