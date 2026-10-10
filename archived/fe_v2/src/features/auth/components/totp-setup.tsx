"use client";

import { QRCodeSVG } from "qrcode.react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { TOTPSetupResponse } from "@/lib/api/generated/model";

function getManualSecret(uri: string): string | null {
  try {
    return new URL(uri).searchParams.get("secret");
  } catch {
    return null;
  }
}

export function TotpSetup({
  setup,
  busy,
  error,
  onConfirm,
}: {
  setup: TOTPSetupResponse;
  busy: boolean;
  error: string | null;
  onConfirm: (code: string) => void;
}) {
  const [code, setCode] = useState("");
  const secret = useMemo(() => getManualSecret(setup.provisioning_uri), [setup.provisioning_uri]);

  return (
    <section className="space-y-5" aria-labelledby="totp-setup-title">
      <div>
        <h2 id="totp-setup-title" className="font-heading text-xl font-bold">
          Set up two-step verification
        </h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Scan this QR code with an authenticator app, then enter the current six-digit code.
        </p>
      </div>

      <div className="flex justify-center rounded-2xl border border-[var(--compass-border)] bg-white p-5">
        <QRCodeSVG
          value={setup.provisioning_uri}
          size={200}
          level="M"
          aria-label="Authenticator setup QR code"
        />
      </div>

      {secret ? (
        <div className="rounded-xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 text-sm">
          <p className="font-semibold">Can’t scan the QR code?</p>
          <p className="mt-1 text-muted-foreground">Enter this setup key manually:</p>
          <code className="mt-2 block break-all select-all font-mono text-xs">{secret}</code>
        </div>
      ) : null}

      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          onConfirm(code.trim());
        }}
      >
        <div className="space-y-2">
          <Label htmlFor="totp-code">Authenticator code</Label>
          <Input
            id="totp-code"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            required
            autoFocus
          />
        </div>

        {error ? (
          <p className="text-sm text-destructive" role="alert" aria-live="polite">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="w-full" disabled={busy || code.trim().length !== 6}>
          {busy ? "Verifying…" : "Verify and continue"}
        </Button>
      </form>
    </section>
  );
}
