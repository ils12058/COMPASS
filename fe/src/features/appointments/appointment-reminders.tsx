"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { compassFetch } from "@/lib/api/client";

type Row = {
  appointment_id: string;
  reference_code: string | null;
  student_name: string | null;
  eligible: boolean;
  reason: string;
  accepted?: boolean;
};
type Preview = { data: { items: Row[] } };
type Result = { data: { items: Row[]; accepted: number; skipped: number } };

export const reminderReason = (code: string): string => ({
  ELIGIBLE: "Ready to send",
  QUEUED: "Reminder added to the notification queue",
  COOLDOWN: "A reminder was sent recently. Try again after three hours.",
  TOO_SOON: "This appointment starts in less than 15 minutes.",
  NOT_SCHEDULED: "Only scheduled appointments can receive reminders.",
  RECIPIENT_INACTIVE: "The student account is not active.",
  NOT_AVAILABLE: "This appointment is not available to you.",
}[code] ?? "This appointment is not available for reminders.");

export function ReminderSender({
  selected, onClose, open, onComplete,
}: { selected: string[]; open: boolean; onClose: () => void; onComplete?: () => void }) {
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<Row[] | null>(null);
  const [results, setResults] = useState<Row[] | null>(null);
  const [requestKey, setRequestKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selection = selected.join(",");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setPreview(null);
    setResults(null);
    setError(null);
    setRequestKey(crypto.randomUUID());
    void compassFetch<Preview>("/api/v1/appointments/reminders/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ appointment_ids: selected }),
    }).then((response) => {
      if (!cancelled) setPreview(response.data.items);
    }).catch(() => {
      if (!cancelled) setError("We couldn't check the selected appointments. Close and try again.");
    });
    return () => { cancelled = true; };
  // The caller must keep the selection unchanged while the preview is displayed.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, selection]);

  async function send() {
    if (!preview || busy || results) return;
    setBusy(true);
    setError(null);
    try {
      const response = await compassFetch<Result>("/api/v1/appointments/reminders/send", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ appointment_ids: selected, request_key: requestKey }),
      });
      setResults(response.data.items);
      await queryClient.invalidateQueries({ queryKey: ["/api/v1/appointments"] });
      onComplete?.();
    } catch {
      setError("We couldn't confirm the reminder request. Try again using the same confirmation.");
    } finally {
      setBusy(false);
    }
  }

  const rows = results ?? preview ?? [];
  const available = rows.filter((item) => item.eligible).length;
  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next && !busy) onClose(); }}>
      <DialogContent dismissible={!busy}>
        <DialogTitle>{selected.length === 1 ? "Send appointment reminder" : "Send appointment reminders"}</DialogTitle>
        <DialogDescription>
          Review the students below before sending. Reminders appear in COMPASS first; email and browser notifications may still be pending.
        </DialogDescription>
        {preview === null && !error ? <p role="status" className="mt-4 text-sm text-muted">Checking appointments…</p> : null}
        <ul className="mt-4 max-h-72 space-y-3 overflow-y-auto text-sm" aria-label="Reminder recipients">
          {rows.map((row) => (
            <li key={row.appointment_id} className="rounded-md border border-border p-3">
              <p className="font-medium text-ink">{row.student_name ?? "Unavailable appointment"}</p>
              {row.reference_code ? <p className="text-muted">{row.reference_code}</p> : null}
              <p className="mt-1 text-muted">{results && row.accepted ? "Reminder queued. Email and browser delivery are pending." : reminderReason(row.reason)}</p>
            </li>
          ))}
        </ul>
        {results ? <p role="status" className="mt-3 text-sm">{results.filter((r) => r.accepted).length} accepted, {results.filter((r) => !r.accepted).length} skipped.</p> : null}
        {error ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
        <div className="mt-5 flex flex-wrap gap-2">
          {!results ? <Button onClick={() => void send()} disabled={!preview || available === 0 || busy} aria-busy={busy}>
            {busy ? "Sending requests…" : `Confirm ${available} reminder${available === 1 ? "" : "s"}`}
          </Button> : null}
          <Button variant="secondary" disabled={busy} onClick={onClose}>{results ? "Done" : "Cancel"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
