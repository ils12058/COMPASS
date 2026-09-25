"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { reportErrorMessage } from "@/features/reports/reports-shared";
import { downloadBinaryResponse } from "@/lib/browser-download";
import type { ReportsDownloadGraduateTracerXlsxParams } from "@/lib/api/generated/model";
import { reportsDownloadGraduateTracerXlsx } from "@/lib/api/generated/reports/reports";

export function GraduateTracerDownload({
  params,
}: {
  params: ReportsDownloadGraduateTracerXlsxParams;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      const response = await reportsDownloadGraduateTracerXlsx(params);
      downloadBinaryResponse(response, "COMPASS-Graduate-Tracer.xlsx");
    } catch (caught) {
      setError(
        reportErrorMessage(
          caught,
          "The Graduate Tracer XLSX could not be downloaded.",
        ),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div aria-busy={pending}>
      <Button
        variant="secondary"
        disabled={pending}
        onClick={() => void download()}
      >
        {pending ? "Preparing XLSX…" : "Download XLSX"}
      </Button>
      {error ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
