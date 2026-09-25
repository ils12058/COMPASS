"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { reportErrorMessage } from "@/features/reports/reports-shared";
import { downloadBinaryResponse } from "@/lib/browser-download";
import type {
  ReportsDownloadStudentProfilePdfParams,
  ReportsDownloadStudentProfileXlsxParams,
} from "@/lib/api/generated/model";
import {
  reportsDownloadStudentProfilePdf,
  reportsDownloadStudentProfileXlsx,
} from "@/lib/api/generated/reports/reports";

export function StudentProfileDownloads({
  params,
}: {
  params: ReportsDownloadStudentProfilePdfParams &
    ReportsDownloadStudentProfileXlsxParams;
}) {
  const [pending, setPending] = useState({ pdf: false, xlsx: false });
  const [errors, setErrors] = useState<{
    pdf: string | null;
    xlsx: string | null;
  }>({ pdf: null, xlsx: null });

  async function downloadPdf() {
    if (pending.pdf) return;
    setPending((current) => ({ ...current, pdf: true }));
    setErrors((current) => ({ ...current, pdf: null }));
    try {
      const response = await reportsDownloadStudentProfilePdf(params);
      downloadBinaryResponse(response, "COMPASS-Student-Profiling.pdf");
    } catch (error) {
      setErrors((current) => ({
        ...current,
        pdf: reportErrorMessage(
          error,
          "The Student Profiling PDF could not be downloaded.",
        ),
      }));
    } finally {
      setPending((current) => ({ ...current, pdf: false }));
    }
  }

  async function downloadXlsx() {
    if (pending.xlsx) return;
    setPending((current) => ({ ...current, xlsx: true }));
    setErrors((current) => ({ ...current, xlsx: null }));
    try {
      const response = await reportsDownloadStudentProfileXlsx(params);
      downloadBinaryResponse(response, "COMPASS-Student-Profiling.xlsx");
    } catch (error) {
      setErrors((current) => ({
        ...current,
        xlsx: reportErrorMessage(
          error,
          "The Student Profiling XLSX could not be downloaded.",
        ),
      }));
    } finally {
      setPending((current) => ({ ...current, xlsx: false }));
    }
  }

  return (
    <div
      aria-busy={pending.pdf || pending.xlsx}
      className="flex flex-wrap gap-2"
    >
      <Button
        variant="secondary"
        disabled={pending.pdf}
        onClick={() => void downloadPdf()}
      >
        {pending.pdf ? "Preparing PDF…" : "Download PDF"}
      </Button>
      <Button
        variant="secondary"
        disabled={pending.xlsx}
        onClick={() => void downloadXlsx()}
      >
        {pending.xlsx ? "Preparing XLSX…" : "Download XLSX"}
      </Button>
      {errors.pdf ? (
        <p role="alert" className="basis-full text-sm text-danger">
          {errors.pdf}
        </p>
      ) : null}
      {errors.xlsx ? (
        <p role="alert" className="basis-full text-sm text-danger">
          {errors.xlsx}
        </p>
      ) : null}
    </div>
  );
}
