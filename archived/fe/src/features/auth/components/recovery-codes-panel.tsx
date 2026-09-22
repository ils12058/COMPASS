"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

export function RecoveryCodesPanel({
  codes,
  onDone,
}: {
  codes: string[];
  onDone: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copyCodes() {
    await navigator.clipboard.writeText(codes.join("\n"));
    setCopied(true);
  }

  return (
    <section className="space-y-4" aria-labelledby="recovery-codes-title">
      <div>
        <h2 id="recovery-codes-title" className="font-heading text-xl font-bold">
          Save your recovery codes
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Save these recovery codes now. Each code can be used once if you lose access to your
          authenticator. COMPASS cannot show this same set again later.
        </p>
      </div>

      <div
        className="grid gap-2 rounded-lg border bg-muted p-4 font-mono text-sm sm:grid-cols-2"
        aria-label="Recovery codes"
      >
        {codes.map((code) => (
          <span key={code} className="select-text">
            {code}
          </span>
        ))}
      </div>

      <Button variant="outline" onClick={copyCodes}>
        {copied ? "Copied" : "Copy all codes"}
      </Button>

      <label className="flex items-start gap-3 text-sm">
        <input
          className="mt-1 size-4"
          type="checkbox"
          checked={acknowledged}
          onChange={(event) => setAcknowledged(event.target.checked)}
        />
        <span>I saved these recovery codes somewhere secure.</span>
      </label>

      <Button disabled={!acknowledged} onClick={onDone}>
        Continue
      </Button>
    </section>
  );
}
