"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ecounselingErrorMessage } from "./ecounseling-shared";
import { eCounselingAccessAssignedMedia } from "@/lib/api/generated/e-counseling/e-counseling";
import type { ECounselingMediaKind, RecordingWorkspaceState } from "@/lib/api/generated/model";

export function MediaArtifactDownload({ appointmentId, kind, state, canAccess }: {
  appointmentId: string;
  kind: ECounselingMediaKind;
  state: Pick<RecordingWorkspaceState, "artifact_status" | "artifact_available" | "artifact_disposed_at">;
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
      // An imperative generated request keeps the signed URL out of query/mutation caches.
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
  if (state.artifact_disposed_at || state.artifact_status === "DISPOSED") {
    return <p className="mt-2 text-sm text-muted">Deleted under an approved retention rule.</p>;
  }
  if (state.artifact_status === "PENDING" || state.artifact_status === "PROCESSING") {
    return <p role="status" className="mt-2 text-sm text-muted">Preparing {subject}…</p>;
  }
  if (state.artifact_status === "FAILED") {
    return <p className="mt-2 text-sm text-muted">{"The file isn't available right now. Preparation will be retried."}</p>;
  }
  return state.artifact_available && canAccess ? <div className="mt-3">
    <Button variant="secondary" disabled={pending} onClick={() => void download()}>
      {pending ? "Preparing download…" : `Download ${subject}`}
    </Button>
    {error ? <p role="alert" className="mt-2 text-sm text-danger">{error}</p> : null}
  </div> : null;
}
