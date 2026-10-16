"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Download, Printer } from "lucide-react";

import { Button } from "@/components/ui/button";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { GoodMoralFulfillmentNotice } from "@/features/good-moral/good-moral-pdf";
import { openGoodMoralPrintPreview } from "@/features/good-moral/good-moral-print-preview";
import { goodMoralDownloadCertificate, useGoodMoralDownloadCertificate } from "@/lib/api/generated/good-moral/good-moral";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { institutionalPdfFallbackFilename } from "@/lib/institutional-pdf-filenames";

function CertificatePreview({ blob }: { blob: Blob }) {
  const frame = useRef<HTMLIFrameElement>(null);
  useEffect(() => {
    const element = frame.current;
    if (!element) return;
    const url = URL.createObjectURL(blob);
    element.src = url;
    return () => {
      element.removeAttribute("src");
      URL.revokeObjectURL(url);
    };
  }, [blob]);
  return <iframe ref={frame} title="Finalized certificate PDF" className="h-96 w-full rounded-sm border border-border sm:h-[32rem]" />;
}

// Mount only for a confirmed ISSUED operational record with can_download. This read has no path
// back to the issue mutation; retrying a PDF or cancelling browser printing cannot reissue it.
export function GoodMoralIssuedPdf({ requestId }: { requestId: string }) {
  const pdf = useGoodMoralDownloadCertificate(requestId, {
    // Share the in-flight read across observer replay. With gcTime zero, an unobserved
    // response is discarded on completion, including after permission loss or navigation.
    query: { queryFn: () => goodMoralDownloadCertificate(requestId), retry: false, staleTime: Infinity, gcTime: 0, refetchOnWindowFocus: false, refetchOnReconnect: false },
  });
  const response = safeQueryData(pdf);
  const helpId = useId();
  const [printError, setPrintError] = useState<string | null>(null);

  function print() {
    if (!response || pdf.isFetching) return;
    setPrintError(openGoodMoralPrintPreview(response.data) ? null : "The PDF preview was blocked. Allow a new tab and try again, or download the certificate to print it.");
  }

  async function download() {
    const available = response ?? safeQueryData(await pdf.refetch());
    if (available) downloadBinaryResponse(available, institutionalPdfFallbackFilename("goodMoral", requestId));
  }

  return (
    <div className="space-y-3">
      <p role="status" className="text-sm leading-6 text-muted">The certificate has been issued. You can print or download the finalized PDF.</p>
      <div className="flex flex-wrap gap-3">
        <Button onClick={print} aria-describedby={helpId} disabled={!response || pdf.isFetching}>
          <Printer aria-hidden="true" size={16} />Print certificate
        </Button>
        <Button variant="secondary" onClick={() => void download()} disabled={pdf.isFetching}>
          <Download aria-hidden="true" size={16} />Download certificate
        </Button>
      </div>
      {pdf.isFetching ? <p role="status" className="text-sm text-muted">Preparing certificate PDF…</p> : null}
      {pdf.isError ? (
        <div className="space-y-2">
          <p role="alert" className="max-w-lg text-sm leading-6 text-danger">The certificate is issued, but its PDF could not be prepared. Retry the PDF without issuing again.</p>
          <Button variant="secondary" onClick={() => void pdf.refetch()} disabled={pdf.isFetching}>Retry PDF</Button>
        </div>
      ) : null}
      {printError ? <p role="alert" className="max-w-lg text-sm leading-6 text-danger">{printError}</p> : null}
      <p id={helpId} className="max-w-2xl text-sm leading-6 text-muted">Print certificate opens the PDF in a new tab. Use the PDF viewer’s Print action or your device’s print command. If your browser cannot preview PDFs, download the certificate and print it from a PDF application.</p>
      <GoodMoralFulfillmentNotice />
      {response ? <CertificatePreview blob={response.data} /> : null}
    </div>
  );
}
