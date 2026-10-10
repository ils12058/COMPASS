"use client";

import { useState } from "react";
import { Download } from "lucide-react";

import { PageAction } from "@/components/ui/page-action";
import {
  exitInterviewsDownloadMyPdf,
  exitInterviewsDownloadPdf,
} from "@/lib/api/generated/exit-interviews/exit-interviews";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { institutionalPdfFallbackFilename } from "@/lib/institutional-pdf-filenames";

export function ExitInterviewPdfDownload({
  exitInterviewId,
  studentFacing,
}: {
  exitInterviewId: string;
  studentFacing: boolean;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setPending(true);
    setError(null);
    try {
      const response = studentFacing
        ? await exitInterviewsDownloadMyPdf(exitInterviewId)
        : await exitInterviewsDownloadPdf(exitInterviewId);
      downloadBinaryResponse(response, institutionalPdfFallbackFilename("exitInterview", exitInterviewId));
    } catch {
      setError("The submitted Exit Interview PDF could not be released right now. Try again later.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <PageAction icon={Download} variant="secondary" onClick={() => void download()} disabled={pending} aria-busy={pending} label={pending ? "Preparing PDF…" : "Download PDF"} />
      {error ? <p role="alert" className="max-w-lg text-sm text-danger">{error}</p> : null}
    </div>
  );
}
