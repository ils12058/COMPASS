"use client";

import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { getAssessmentRecordsListQueryKey } from "@/lib/api/generated/assessment-records/assessment-records";
import { getAssessmentRecordsAccess } from "./assessment-records-access";

export const assessmentContentFields = [
  { key: "score", label: "Score / rating", maximum: 500 },
  { key: "result", label: "Result", maximum: 4000 },
  { key: "interpretation", label: "Interpretation", maximum: 8000 },
  { key: "remarks", label: "Remarks", maximum: 4000 },
] as const;

export function AssessmentUnavailable() {
  return (
    <WorkspaceUnavailable title="Assessment Records unavailable">
      You don’t have access to assessment records.
    </WorkspaceUnavailable>
  );
}

export function AssessmentGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return getAssessmentRecordsAccess(user).canView ? (
    children
  ) : (
    <AssessmentUnavailable />
  );
}

export function assessmentErrorMessage(error: unknown): string {
  if (error instanceof CompassApiError) {
    const code = readApiErrorCode(error.body);
    if (code === "csrf_failed")
      return "The security check expired. Try saving again.";
    if (code === "assessment_record_content_unavailable")
      return "The confidential assessment content is unavailable. Contact the Guidance Office administrator.";
    if (error.status === 403)
      return "You don't have access to these assessment records.";
    if (error.status === 404)
      return "The requested Assessment Record is not available.";
    if (error.status === 409)
      return "An Assessment Type with this name already exists. Choose another name.";
    if (error.status === 422)
      return "Check the selected Student, Assessment Type, date and result fields, then try again.";
  }
  return "Assessment Records could not be loaded or saved. Try again.";
}

export function AssessmentError({
  error,
  retry,
  pending = false,
}: {
  error: unknown;
  retry: () => void;
  pending?: boolean;
}) {
  return (
    <Notice
      role="alert"
      tone="danger"
      action={
        <Button
          type="button"
          variant="secondary"
          disabled={pending}
          onClick={retry}
        >
          {pending ? "Retrying…" : "Retry"}
        </Button>
      }
    >
      {assessmentErrorMessage(error)}
    </Notice>
  );
}

export function AssessmentLoading({ framed = true }: { framed?: boolean }) {
  return <RowsSkeleton label="Loading assessment records…" framed={framed} />;
}

export function safeAssessmentDetail<T>(query: {
  data?: T;
  error: unknown;
  isError: boolean;
  isPlaceholderData?: boolean;
}) {
  // A rejected envelope must also conceal any previously cached confidential projection.
  if (
    query.error instanceof CompassApiError &&
    readApiErrorCode(query.error.body) ===
      "assessment_record_content_unavailable"
  )
    return undefined;
  return safeQueryData(query);
}

export function useAssessmentRefresh() {
  const client = useQueryClient();
  const root = getAssessmentRecordsListQueryKey()[0];
  return () =>
    client.invalidateQueries({
      predicate: (query) =>
        typeof query.queryKey[0] === "string" &&
        typeof root === "string" &&
        (query.queryKey[0] === root ||
          query.queryKey[0].startsWith(root + "/")),
    });
}
