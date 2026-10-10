"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export type LoginMfaMethod = "totp" | "recovery";

export function LoginMfaForm({
  methods,
  challengeExpiresAt,
  busy,
  error,
  onSubmit,
  onStartOver,
}: {
  methods: string[];
  challengeExpiresAt: string | null;
  busy: boolean;
  error: string | null;
  onSubmit: (method: LoginMfaMethod, code: string) => Promise<void>;
  onStartOver: () => void;
}) {
  const [method, setMethod] = useState<LoginMfaMethod>(
    methods.includes("totp") ? "totp" : "recovery",
  );
  const [code, setCode] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = code.trim();
    setCode("");
    await onSubmit(method, value);
  }

  const recoveryAvailable = methods.includes("recovery");

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="space-y-1">
        <h2 className="font-heading text-xl font-bold">Verify your sign-in</h2>
        {challengeExpiresAt ? (
          <p className="text-sm text-muted-foreground">
            This verification request expires at{" "}
            {new Date(challengeExpiresAt).toLocaleTimeString([], {
              hour: "numeric",
              minute: "2-digit",
            })}
            .
          </p>
        ) : null}
      </div>

      {recoveryAvailable ? (
        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Verification method</legend>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="mfa-method"
              value="totp"
              checked={method === "totp"}
              onChange={() => {
                setMethod("totp");
                setCode("");
              }}
            />
            Authenticator code
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="mfa-method"
              value="recovery"
              checked={method === "recovery"}
              onChange={() => {
                setMethod("recovery");
                setCode("");
              }}
            />
            Recovery code
          </label>
        </fieldset>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor="login-mfa-code">
          {method === "recovery" ? "Recovery code" : "Authenticator code"}
        </Label>
        <Input
          id="login-mfa-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          inputMode={method === "totp" ? "numeric" : "text"}
          autoComplete={method === "totp" ? "one-time-code" : "off"}
          maxLength={method === "totp" ? 6 : 32}
          required
          autoFocus
        />
      </div>

      {error ? (
        <p role="alert" aria-live="polite" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || !code.trim()}>
          {busy ? "Verifying…" : "Verify and sign in"}
        </Button>
        <Button type="button" variant="ghost" onClick={onStartOver}>
          Start over
        </Button>
      </div>
    </form>
  );
}
