"use client";

import { useState } from "react";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { goodMoralErrorMessage } from "@/features/good-moral/good-moral-shared";
import { goodMoralDownloadCertificate, goodMoralDownloadMyCertificate } from "@/lib/api/generated/good-moral/good-moral";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { institutionalPdfFallbackFilename } from "@/lib/institutional-pdf-filenames";

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
      downloadBinaryResponse(response, institutionalPdfFallbackFilename("goodMoral", requestId));
    } catch (caught) {
      setError(goodMoralErrorMessage(caught, "Couldn't release the certificate right now. Try again later."));
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
      <GoodMoralFulfillmentNotice />
      {error ? <p role="alert" className="max-w-lg text-sm text-danger">{error}</p> : null}
    </div>
  );
}

export function GoodMoralFulfillmentNotice() {
  return <p className="max-w-lg text-sm leading-6 text-muted">The printed certificate needs the issuer’s handwritten signature and dry seal. The printed name alone is not a signature.</p>;
}
