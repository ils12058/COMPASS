"use client";

import { useState } from "react";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { goodMoralErrorMessage } from "@/features/good-moral/good-moral-shared";
import { goodMoralDownloadCertificate, goodMoralDownloadMyCertificate } from "@/lib/api/generated/good-moral/good-moral";
import { downloadBinaryResponse } from "@/lib/browser-download";

export function GoodMoralPdfDownload({
  requestId,
  studentFacing,
}: {
  requestId: string;
  studentFacing: boolean;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setPending(true);
    setError(null);
    try {
      const response = studentFacing
        ? await goodMoralDownloadMyCertificate(requestId)
        : await goodMoralDownloadCertificate(requestId);
      downloadBinaryResponse(response, "good-moral-certificate.pdf");
    } catch (caught) {
      setError(goodMoralErrorMessage(caught, "The certificate could not be released right now. Try again later."));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <Button variant="secondary" onClick={() => void download()} disabled={pending}>
        <Download aria-hidden="true" size={16} />
        {pending ? "Preparing certificate…" : "Download certificate"}
      </Button>
      {error ? <p role="alert" className="max-w-lg text-sm text-danger">{error}</p> : null}
    </div>
  );
}
