"use client";

import { FileSpreadsheet } from "lucide-react";
import { useState } from "react";

import { PageAction } from "@/components/ui/page-action";
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
    <div aria-busy={pending} className="flex max-w-xs flex-col gap-2 sm:items-end">
      <PageAction
        icon={FileSpreadsheet}
        variant="secondary"
        label={pending ? "Preparing XLSX…" : "Download XLSX"}
        disabled={pending}
        onClick={() => void download()}
      />
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
