"use client";

import { Check, Copy } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { useMemo, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthFlow } from "@/features/auth/components/auth-flow-context";
import { FormError } from "@/features/auth/components/auth-states";
import { authErrorMessage } from "@/features/auth/utils/errors";
import {
  useAuthConfirmMandatoryTotpBootstrap,
  useAuthStartMandatoryTotpBootstrap,
} from "@/lib/api/generated/auth/auth";
import type { TOTPSetupResponse } from "@/lib/api/generated/model";

function readManualSecret(provisioningUri: string): string | null {
  try {
    const uri = new URL(provisioningUri);
    const secret = uri.protocol === "otpauth:" ? uri.searchParams.get("secret") : null;
    return secret && /^[A-Z2-7]+=*$/i.test(secret) ? secret : null;
  } catch {
    return null;
  }
}

function RecoveryCodes({ codes, nextPath }: { codes: string[]; nextPath: string }) {
  const flow = useAuthFlow();
  const router = useRouter();
  const [acknowledged, setAcknowledged] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copyAll() {
    await navigator.clipboard.writeText(codes.join("\n"));
    setCopied(true);
  }

  function returnToSignIn() {
    flow.clearFlow();
    router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
  }

  return (
    <section aria-labelledby="recovery-codes-heading">
      <h1 id="recovery-codes-heading" className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">
        Save your recovery codes
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        Keep these codes somewhere secure. Each code can be used once if you cannot access your authenticator app.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-x-4 gap-y-2 border-y border-border bg-surface-subtle p-4 font-mono text-sm text-ink" aria-label="Recovery codes">
        {codes.map((code) => <code key={code} className="break-all">{code}</code>)}
      </div>

      <Button type="button" variant="secondary" className="mt-4" onClick={() => void copyAll()}>
        {copied ? <Check size={17} aria-hidden="true" /> : <Copy size={17} aria-hidden="true" />}
        {copied ? "Copied" : "Copy all"}
      </Button>

      <label className="mt-6 flex items-start gap-3 text-sm text-ink">
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(event) => setAcknowledged(event.target.checked)}
          className="mt-1 size-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        />
        <span className="font-semibold">I have saved my recovery codes.</span>
      </label>

      <Button type="button" className="mt-5 w-full" disabled={!acknowledged} onClick={returnToSignIn}>
        Return to sign in
      </Button>
    </section>
  );
}

export function MandatoryTotpSetup() {
  const flow = useAuthFlow();
  const [setup, setSetup] = useState<TOTPSetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const start = useAuthStartMandatoryTotpBootstrap();
  const confirm = useAuthConfirmMandatoryTotpBootstrap();
  const manualSecret = useMemo(
    () => (setup ? readManualSecret(setup.provisioning_uri) : null),
    [setup],
  );

  if (!flow.mandatorySetup) {
    return (
      <section>
        <h1 className="font-heading text-3xl font-bold text-ink">Restart sign in</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          The authenticator setup challenge is no longer available.
        </p>
        <Link className="mt-6 inline-flex min-h-10 items-center font-semibold text-brand hover:underline" href="/login">
          Return to sign in
        </Link>
      </section>
    );
  }

  if (recoveryCodes) return <RecoveryCodes codes={recoveryCodes} nextPath={flow.nextPath} />;

  async function startSetup() {
    setError(null);
    try {
      const response = await start.mutateAsync();
      setSetup(response.data);
    } catch (caught) {
      setError(authErrorMessage(caught, "Authenticator setup could not be started. Please try again."));
    }
  }

  async function confirmSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const response = await confirm.mutateAsync({ data: { code } });
      setRecoveryCodes(response.data.recovery_codes);
      setCode("");
    } catch (caught) {
      setError(authErrorMessage(caught, "The authenticator code could not be verified."));
    }
  }

  if (!setup) {
    return (
      <section aria-labelledby="setup-heading">
        <h1 id="setup-heading" className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          Set up an authenticator app
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Additional account security is required before this account can sign in to COMPASS.
        </p>
        <FormError id="setup-start-error" message={error} />
        <Button className="mt-5 w-full" disabled={start.isPending} onClick={() => void startSetup()}>
          {start.isPending ? "Starting setup…" : "Start authenticator setup"}
        </Button>
      </section>
    );
  }

  return (
    <section aria-labelledby="setup-heading">
      <h1 id="setup-heading" className="font-heading text-3xl font-bold tracking-tight text-ink">
        Set up an authenticator app
      </h1>
      <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm leading-6 text-muted">
        <li>Scan the QR code with an authenticator app.</li>
        <li>Enter the current verification code.</li>
        <li>Confirm setup.</li>
      </ol>

      <div className="mt-6 flex justify-center border-y border-border bg-surface-raised py-6">
        <QRCodeSVG value={setup.provisioning_uri} size={220} level="M" marginSize={2} title="Authenticator setup QR code" />
      </div>

      {manualSecret ? (
        <details className="mt-4 border-b border-border pb-4 text-sm">
          <summary className="cursor-pointer font-semibold text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            Enter a setup key instead
          </summary>
          <p className="mt-3 text-muted">Use this key only in your authenticator app:</p>
          <code className="mt-2 block break-all bg-surface-muted p-3 font-mono text-ink">{manualSecret}</code>
        </details>
      ) : null}

      <form className="mt-6 space-y-5" onSubmit={confirmSetup}>
        <div className="grid gap-2">
          <Label htmlFor="setup-code">Authenticator code</Label>
          <Input
            id="setup-code"
            name="code"
            autoComplete="one-time-code"
            inputMode="numeric"
            maxLength={6}
            required
            value={code}
            onChange={(event) => setCode(event.target.value)}
            aria-describedby={error ? "setup-error" : undefined}
          />
        </div>
        <FormError id="setup-error" message={error} />
        <Button type="submit" className="w-full" disabled={confirm.isPending}>
          {confirm.isPending ? "Confirming…" : "Confirm authenticator"}
        </Button>
      </form>
    </section>
  );
}
