"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { eCounselingAccessAssignedMedia } from "@/lib/api/generated/e-counseling/e-counseling";
import type { ECounselingMediaKind, RecordingWorkspaceState } from "@/lib/api/generated/model";

import { ecounselingErrorMessage } from "./ecounseling-shared";

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
  const subject = kind === "RECORDING" ? "recording" : "transcript";

  async function download() {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      const result = await eCounselingAccessAssignedMedia(appointmentId, kind, { cache: "no-store" });
      const link = document.createElement("a");
      link.href = result.data.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.referrerPolicy = "no-referrer";
      link.click();
      link.remove();
    } catch (caught) {
      setError(ecounselingErrorMessage(caught, "The file isn't available right now. Try again."));
    } finally {
      setPending(false);
    }
  }

  if (!(state.artifact_status === "STORED" && state.artifact_available && !state.artifact_disposed_at && canAccess)) return null;
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
