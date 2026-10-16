"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { eCounselingAccessAssignedMedia } from "@/lib/api/generated/e-counseling/e-counseling";
import type { ECounselingMediaKind, RecordingWorkspaceState } from "@/lib/api/generated/model";

import { ecounselingErrorMessage } from "./ecounseling-shared";
import { ecounselingResourceAccess } from "./ecounseling-resource-access";
import { useECounselingResourceDenial } from "./use-ecounseling-resource-access";
import { isSessionEndedError } from "@/features/freshness/query-freshness";
import { requestSessionRevalidation } from "@/lib/auth/session-revalidation";

type ArtifactState = Pick<RecordingWorkspaceState, "artifact_status" | "artifact_available" | "artifact_disposed_at">;

export type FileOutcome = { text: string; short: "ready" | "preparing" | "deleted" | "not available" | "saved" };

// The file's outcome in words, from the COMPASS artifact state (ADR-092) rather than capture or
// provider settings. `short` is the few words a collapsed summary shows.
export function artifactOutcome(kind: ECounselingMediaKind, state: ArtifactState): FileOutcome | null {
  if (state.artifact_disposed_at || state.artifact_status === "DISPOSED") return { text: "Deleted under an approved retention rule.", short: "deleted" };
  if (state.artifact_status === "PENDING" || state.artifact_status === "PROCESSING") return { text: "Preparing file…", short: "preparing" };
  if (state.artifact_status === "FAILED") return { text: "The file isn't available right now. Preparation will be retried.", short: "not available" };
  if (state.artifact_status === "STORED") return state.artifact_available ? { text: "Ready", short: kind === "RECORDING" ? "ready" : "saved" } : { text: "Saved", short: "saved" };
  return null;
}

// A download for an assigned Counselor. Each click asks the backend for a fresh, short-lived link
// with the generated imperative client and `no-store`, so links never enter query or mutation
// caches or component state, and nothing is fetched before the click.
export function MediaArtifactDownload({ appointmentId, kind, state, canAccess }: {
  appointmentId: string;
  kind: ECounselingMediaKind;
  state: ArtifactState;
  canAccess: boolean;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resourceAccess = ecounselingResourceAccess(useQueryClient());
  const denial = useECounselingResourceDenial(appointmentId);
  const subject = kind === "RECORDING" ? "recording" : "transcript";

  async function download() {
    if (pending || resourceAccess.getDenial(appointmentId)) return;
    const downloadWindow = window.open("about:blank", "_blank");
    if (!downloadWindow) {
      setError("Allow pop-ups for COMPASS, then try again.");
      return;
    }
    downloadWindow.opener = null;
    const referrerPolicy = downloadWindow.document.createElement("meta");
    referrerPolicy.name = "referrer";
    referrerPolicy.content = "no-referrer";
    downloadWindow.document.head.append(referrerPolicy);
    downloadWindow.document.body.textContent = "Preparing file…";
    const epoch = resourceAccess.epoch(appointmentId);
    setPending(true);
    setError(null);
    try {
      const result = await eCounselingAccessAssignedMedia(appointmentId, kind, { cache: "no-store" });
      resourceAccess.assertAuthorized(appointmentId, epoch);
      if (downloadWindow.closed) return;
      const link = downloadWindow.document.createElement("a");
      link.href = result.data.url;
      link.referrerPolicy = "no-referrer";
      link.rel = "noopener noreferrer";
      link.textContent = "Download is starting…";
      downloadWindow.document.body.replaceChildren(link);
      link.click();
    } catch (caught) {
      downloadWindow.close();
      resourceAccess.requestFailed(caught);
      if (isSessionEndedError(caught)) requestSessionRevalidation("session");
      setError(ecounselingErrorMessage(caught, "The file isn't available right now. Try again."));
    } finally {
      setPending(false);
    }
  }

  if (denial || !(state.artifact_status === "STORED" && state.artifact_available && !state.artifact_disposed_at && canAccess)) return null;
  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="secondary" className="min-h-10" disabled={pending} aria-label={`Download ${subject}`} onClick={() => void download()}>
        <Download aria-hidden="true" size={16} />
        {pending ? "Preparing…" : "Download"}
      </Button>
      {error ? <p role="alert" className="text-right text-sm text-danger">{error}</p> : null}
    </div>
  );
}
