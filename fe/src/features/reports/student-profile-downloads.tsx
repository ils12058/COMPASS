"use client";

import { FileDown, FileSpreadsheet } from "lucide-react";
import { useState } from "react";

import { PageAction, PageActionGroup } from "@/components/ui/page-action";
import { reportErrorMessage } from "@/features/reports/reports-shared";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { studentProfilingPdfFallbackFilename } from "@/lib/institutional-pdf-filenames";
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
  academicYearLabel,
}: {
  params: ReportsDownloadStudentProfilePdfParams &
    ReportsDownloadStudentProfileXlsxParams;
  academicYearLabel: string;
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
      downloadBinaryResponse(response, studentProfilingPdfFallbackFilename(academicYearLabel));
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
    <div aria-busy={pending.pdf || pending.xlsx} className="flex max-w-xs flex-col gap-2 sm:items-end">
      <PageActionGroup>
        <PageAction
          icon={FileDown}
          variant="secondary"
          label={pending.pdf ? "Preparing PDF…" : "Download PDF"}
          disabled={pending.pdf}
          onClick={() => void downloadPdf()}
        />
        <PageAction
          icon={FileSpreadsheet}
          variant="secondary"
          label={pending.xlsx ? "Preparing XLSX…" : "Download XLSX"}
          disabled={pending.xlsx}
          onClick={() => void downloadXlsx()}
        />
      </PageActionGroup>
      {errors.pdf ? (
        <p role="alert" className="text-sm text-danger">
          {errors.pdf}
        </p>
      ) : null}
      {errors.xlsx ? (
        <p role="alert" className="text-sm text-danger">
          {errors.xlsx}
        </p>
      ) : null}
    </div>
  );
}
