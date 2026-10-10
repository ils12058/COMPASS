"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

export function RecoveryCodesPanel({
  codes,
  doneLabel = "Continue to sign in",
  onDone,
}: {
  codes: string[];
  doneLabel?: string;
  onDone: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  async function copyCodes() {
    setCopyError(null);

    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      setCopied(true);
    } catch {
      setCopyError("Copying was not available. Select the codes and copy them manually.");
    }
  }

  return (
    <section className="space-y-5" aria-labelledby="recovery-codes-title">
      <div>
        <h2 id="recovery-codes-title" className="font-heading text-xl font-bold">
          Save your recovery codes
        </h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Save these codes somewhere secure. Each one works once if you lose access to your
          authenticator, and COMPASS cannot show this set again later.
        </p>
      </div>

      <div
        className="grid gap-2 rounded-xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 font-mono text-sm sm:grid-cols-2"
        aria-label="Recovery codes"
      >
        {codes.map((code) => (
          <span key={code} className="select-text rounded-md bg-white/70 px-2 py-1">
            {code}
          </span>
        ))}
      </div>

      <div className="space-y-2">
        <Button type="button" variant="outline" onClick={copyCodes}>
          {copied ? "Copied" : "Copy all codes"}
        </Button>
        {copyError ? (
          <p className="text-sm text-muted-foreground" role="status">
            {copyError}
          </p>
        ) : null}
      </div>

      <label className="flex items-start gap-3 text-sm leading-6">
        <Checkbox
          checked={acknowledged}
          onCheckedChange={(checked) => setAcknowledged(checked === true)}
          className="mt-1"
        />
        <span>I saved these recovery codes somewhere secure.</span>
      </label>

      <Button className="w-full" disabled={!acknowledged} onClick={onDone}>
        {doneLabel}
      </Button>
    </section>
  );
}
