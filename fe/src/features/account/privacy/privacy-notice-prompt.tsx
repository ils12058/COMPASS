"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import {
  ACKNOWLEDGMENT_HELP,
  acknowledgeErrorMessage,
  nextPendingNotice,
  PENDING_NOTICE_PARAMS,
} from "@/features/account/privacy/privacy-acknowledgment";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import {
  getPrivacyGovernanceListMyNoticesQueryKey,
  usePrivacyGovernanceAcknowledgeMyNotice,
  usePrivacyGovernanceListMyNotices,
} from "@/lib/api/generated/privacy-governance/privacy-governance";
import { formatDateOnly } from "@/lib/institutional-time";

const DEFERRED_KEY = "compass.privacy-notices.not-now";

// "Not now" lasts for this browser tab's session, so the prompt does not return on every page.
// Storage can be unavailable (private windows, blocked site data); the choice then lasts until the
// page reloads.
function readDeferred(): ReadonlySet<string> {
  try {
    const stored = JSON.parse(globalThis.sessionStorage?.getItem(DEFERRED_KEY) ?? "[]");
    return new Set(Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : []);
  } catch {
    return new Set();
  }
}

function writeDeferred(revisions: ReadonlySet<string>) {
  try {
    globalThis.sessionStorage?.setItem(DEFERRED_KEY, JSON.stringify([...revisions]));
  } catch {
    // Keep the in-memory choice only.
  }
}

// Places where a dialog would get in the way: the Privacy page already shows every notice with its
// own Acknowledge button, and a live E-Counseling session must not be interrupted.
export function promptSuppressedOn(pathname: string): boolean {
  return (
    pathname === "/portal/account/privacy" ||
    pathname.startsWith("/portal/account/privacy/") ||
    /^\/portal\/e-counseling\/[^/]+/.test(pathname)
  );
}

// Surfaces a current Privacy Notice that asks this account for an acknowledgment, one at a time.
// Acknowledging records that the notice was seen; it is not consent, and an unacknowledged notice
// never blocks other work: "Not now" closes the prompt and Account › Privacy keeps every notice.
export function PrivacyNoticePrompt() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const pending = usePrivacyGovernanceListMyNotices(PENDING_NOTICE_PARAMS, {
    query: { retry: false },
  });
  const acknowledge = usePrivacyGovernanceAcknowledgeMyNotice();
  const [deferred, setDeferred] = useState<ReadonlySet<string>>(readDeferred);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState<{ revisionId: string; title: string } | null>(
    null,
  );
  // The prompt usually opens by itself with nothing focused; closing it then moves focus to the
  // page content rather than leaving it on the document.
  const focusedBeforeOpen = useRef(false);

  const candidate = nextPendingNotice(pending.data?.data.items);
  // If the pending list could not be reloaded after an acknowledgment, the acknowledged notice is
  // not shown again from the old list.
  const notice = candidate?.revision_id === acknowledged?.revisionId ? undefined : candidate;
  const open =
    notice !== undefined && !deferred.has(notice.revision_id) && !promptSuppressedOn(pathname);

  function notNow() {
    if (!notice || busy) return;
    const next = new Set(deferred).add(notice.revision_id);
    setDeferred(next);
    writeDeferred(next);
    setError(null);
    setAcknowledged(null);
  }

  // The next notice, if any, comes from the refreshed server state; nothing is marked locally.
  async function acknowledgeNotice() {
    if (!notice) return;
    setBusy(true);
    setError(null);
    let recorded: { revisionId: string; title: string } | null = null;
    try {
      await acknowledge.mutateAsync({ revisionId: notice.revision_id, data: {} });
      recorded = { revisionId: notice.revision_id, title: notice.title };
    } catch (caught) {
      setError(acknowledgeErrorMessage(caught));
    }
    // Whether it worked or the notice changed meanwhile, show what the server says is pending.
    await queryClient.invalidateQueries({ queryKey: getPrivacyGovernanceListMyNoticesQueryKey() });
    setAcknowledged(recorded);
    setBusy(false);
  }

  if (!notice) return null;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) notNow(); }}>
      <DialogContent
        className="flex h-[min(calc(100dvh-2rem),40rem)] max-h-[calc(100dvh-2rem)] max-w-2xl flex-col overflow-hidden p-0"
        dismissible={!busy}
        closeLabel="Not now"
        closeClassName="hidden sm:inline-flex"
        onOpenAutoFocus={() => {
          focusedBeforeOpen.current = document.activeElement !== document.body;
        }}
        onCloseAutoFocus={(event) => {
          if (focusedBeforeOpen.current) return;
          const main = document.getElementById("main-content");
          if (!main) return;
          event.preventDefault();
          main.focus();
        }}
      >
        <div className="shrink-0 px-4 pb-3 pt-4 sm:px-6 sm:pb-4 sm:pt-6">
          <DialogTitle className="pr-0 text-lg leading-tight sm:pr-8 sm:text-xl">Privacy notice update</DialogTitle>
          <DialogDescription className="text-xs leading-5 sm:text-sm sm:leading-6">
            <span className="font-semibold text-ink">{notice.title}</span>
            {" · "}Effective {formatDateOnly(notice.effective_on)}
          </DialogDescription>
          {acknowledged ? (
            <p role="status" className="mt-3 text-sm text-success">
              “{acknowledged.title}” acknowledged. Another notice also asks for your acknowledgment.
            </p>
          ) : null}
        </div>
        <div className="relative min-h-0 flex-1">
          <div
            data-privacy-notice-scroll=""
            className="absolute inset-0 overflow-y-auto overscroll-contain border-y border-border px-6 py-4"
          >
            <p className="text-sm leading-6 text-muted">{notice.summary}</p>
            <div className="mt-4">
              <PlainTextBlock text={notice.body} />
            </div>
            <p id="privacy-prompt-acknowledgment-help" className="mt-5 text-xs leading-5 text-muted">
              {ACKNOWLEDGMENT_HELP}
            </p>
          </div>
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 bottom-px h-6 bg-gradient-to-t from-surface-raised to-transparent"
          />
        </div>
        <div className="shrink-0 px-4 pb-4 pt-3 sm:px-6 sm:pb-6 sm:pt-4">
          {error ? <p role="alert" className="mb-3 text-sm text-danger">{error}</p> : null}
          <div data-privacy-notice-actions="" className="flex flex-wrap items-center justify-end gap-2">
            <GuardedPortalLink
              href="/portal/account/privacy"
              className="mr-auto text-xs font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:text-sm"
            >
              All privacy notices
            </GuardedPortalLink>
            <Button variant="secondary" disabled={busy} onClick={notNow} className="px-3 sm:px-4">
              Not now
            </Button>
            <Button
              disabled={busy}
              aria-describedby="privacy-prompt-acknowledgment-help"
              onClick={() => void acknowledgeNotice()}
              className="px-3 sm:px-4"
            >
              {busy ? "Acknowledging…" : "Acknowledge notice"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
