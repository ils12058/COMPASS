"use client";

import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { flushSync } from "react-dom";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import {
  safeQueryData,
  isMutationAuthorityError,
  isSessionEndedError,
} from "@/features/freshness/query-freshness";
import {
  EligibleStudentPicker,
  type EligibleStudentOption,
} from "@/features/portal/components/eligible-student-picker";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  useAssessmentRecordsCreate,
  useAssessmentRecordsEligibleStudents,
  useAssessmentRecordsGet,
  useAssessmentRecordsListTypes,
  useAssessmentRecordsUpdate,
} from "@/lib/api/generated/assessment-records/assessment-records";
import type { AssessmentRecordDetail } from "@/lib/api/generated/model";
import {
  institutionalDateInputValue,
  isFutureInstitutionalDateInput,
} from "@/lib/institutional-time";
import { getAssessmentRecordsAccess } from "./assessment-records-access";
import {
  assessmentContentFields,
  assessmentErrorMessage,
  AssessmentError,
  AssessmentLoading,
  AssessmentUnavailable,
  safeAssessmentDetail,
  useAssessmentRefresh,
} from "./assessment-records-shared";

export type AssessmentDraft = {
  assessment_type_id: string;
  administered_on: string;
  score: string;
  result: string;
  interpretation: string;
  remarks: string;
};

export function assessmentDraftError(
  draft: AssessmentDraft,
  studentId: string | undefined,
): string | null {
  if (!studentId) return "Select a current Student.";
  if (!draft.assessment_type_id) return "Select an active Assessment Type.";
  if (!draft.administered_on)
    return "Enter the date the assessment was administered.";
  if (isFutureInstitutionalDateInput(draft.administered_on))
    return "Administered date cannot be in the future.";
  if (!assessmentContentFields.some((field) => draft[field.key].trim()))
    return "Record at least one score, result, interpretation or remark.";
  return null;
}

export function AssessmentRecordEditorPage({
  recordId,
}: {
  recordId?: string;
}) {
  const { user } = usePortalSession();
  const access = getAssessmentRecordsAccess(user);
  const query = useAssessmentRecordsGet(recordId ?? "", {
    query: { enabled: Boolean(recordId) && access.canManage, retry: false },
  });
  if (!access.canManage) return <AssessmentUnavailable />;
  if (recordId) {
    const record = safeAssessmentDetail(query)?.data;
    if (!record)
      return query.isPending ? (
        <AssessmentLoading />
      ) : (
        <AssessmentError
          error={query.error}
          retry={() => void query.refetch()}
          pending={query.isFetching}
        />
      );
    // A failed refresh must be resolved before presenting confidential content for correction.
    if (query.isError)
      return (
        <AssessmentError
          error={query.error}
          retry={() => void query.refetch()}
          pending={query.isFetching}
        />
      );
    return <AssessmentRecordForm key={recordId} record={record} />;
  }
  return <AssessmentRecordForm />;
}

function AssessmentRecordForm({ record }: { record?: AssessmentRecordDetail }) {
  const router = useRouter();
  const refresh = useAssessmentRefresh();
  const initial: AssessmentDraft = {
    assessment_type_id: record?.assessment_type.id ?? "",
    administered_on: record?.administered_on ?? "",
    score: record?.score ?? "",
    result: record?.result ?? "",
    interpretation: record?.interpretation ?? "",
    remarks: record?.remarks ?? "",
  };
  const [draft, setDraft] = useState(initial);
  const [student, setStudent] = useState<EligibleStudentOption | null>(null);
  const [search, setSearch] = useState("");
  const [lookup, setLookup] = useState({ search: "", page: 1 });
  const [error, setError] = useState<string | null>(null);
  const [concealed, setConcealed] = useState(false);
  const [saved, setSaved] = useState(false);
  const submitLock = useRef(false);
  const create = useAssessmentRecordsCreate();
  const update = useAssessmentRecordsUpdate();
  const pending = create.isPending || update.isPending;
  const types = useAssessmentRecordsListTypes(undefined, {
    query: { retry: false },
  });
  const picker = useAssessmentRecordsEligibleStudents(
    { search: lookup.search || undefined, page: lookup.page, page_size: 20 },
    { query: { enabled: !record, retry: false } },
  );
  const catalog = safeQueryData(types)?.data;
  const students = safeQueryData(picker)?.data;
  const back = record
    ? `/portal/assessment-records/${record.id}`
    : "/portal/assessment-records";
  useUnsavedChangesGuard({
    dirty:
      !saved &&
      !concealed &&
      (Boolean(student) || JSON.stringify(draft) !== JSON.stringify(initial)),
    message: "Your Assessment Record changes have not been saved.",
  });
  function field(name: keyof AssessmentDraft, value: string) {
    setDraft((current) => ({ ...current, [name]: value }));
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitLock.current) return;
    const studentId = record?.student.id ?? student?.id;
    const problem = assessmentDraftError(draft, studentId);
    if (problem || !studentId) {
      setError(problem);
      return;
    }
    submitLock.current = true;
    setError(null);
    try {
      const response = record
        ? await update.mutateAsync({ recordId: record.id, data: draft })
        : await create.mutateAsync({
            data: { ...draft, student_id: studentId },
          });
      // Remove the navigation guard only after the backend confirmed persistence.
      flushSync(() => setSaved(true));
      await refresh();
      router.push(`/portal/assessment-records/${response.data.id}`);
    } catch (failure) {
      if (
        isSessionEndedError(failure) ||
        isMutationAuthorityError(failure) ||
        (failure instanceof CompassApiError &&
          (failure.status === 404 ||
            (record &&
              readApiErrorCode(failure.body) ===
                "assessment_record_content_unavailable")))
      )
        setConcealed(true);
      setError(assessmentErrorMessage(failure));
    } finally {
      submitLock.current = false;
    }
  }
  if (concealed)
    return (
      <Notice role="alert" tone="danger">
        {error}
      </Notice>
    );
  return (
    <>
      <PageHeader
        title={record ? "Edit Assessment Record" : "Record assessment result"}
        back={
          <Link href={back} className={pageBackLinkClass}>
            Back to {record ? "Assessment Record" : "Assessment Records"}
          </Link>
        }
        description={
          record
            ? "Correct the recorded facts or result. Student ownership stays with this record."
            : "Record the result supplied by the Guidance Office for a current Student."
        }
      />
      <Panel>
        <PanelSection title="Student" titleId="assessment-form-student">
          {record ? (
            <>
              <p className="font-semibold">{record.student.display_name}</p>
              <p className="mt-1 text-sm text-muted">
                {record.student.institutional_id ??
                  "Institutional ID not available"}
              </p>
            </>
          ) : (
            <fieldset disabled={pending} className="min-w-0">
              <EligibleStudentPicker
                search={search}
                onSearchChange={setSearch}
                onSearch={() => setLookup({ search: search.trim(), page: 1 })}
                items={students?.items ?? []}
                selectedStudent={student}
                selectedId={student?.id ?? null}
                onSelect={setStudent}
                page={lookup.page}
                hasNext={students?.has_next ?? false}
                isLoading={picker.isPending}
                isError={picker.isError}
                errorMessage={assessmentErrorMessage(picker.error)}
                onRetry={() => void picker.refetch()}
                onPageChange={(page) =>
                  setLookup((current) => ({ ...current, page }))
                }
              />
            </fieldset>
          )}
        </PanelSection>
        <form
          onSubmit={(event) => void submit(event)}
          aria-label={
            record ? "Correct Assessment Record" : "Record assessment result"
          }
        >
          <fieldset disabled={pending} className="min-w-0">
            <PanelSection title="Assessment" titleId="assessment-form-facts">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="assessment-type">Assessment Type</Label>
                  <Select
                    id="assessment-type"
                    required
                    value={draft.assessment_type_id}
                    onChange={(event) =>
                      field("assessment_type_id", event.target.value)
                    }
                    disabled={!catalog || types.isError}
                  >
                    <option value="">Select Assessment Type</option>
                    {record && !record.assessment_type.is_active ? (
                      <option value={record.assessment_type.id}>
                        {record.assessment_type.name} (inactive · historical)
                      </option>
                    ) : null}
                    {catalog
                      ?.filter((type) => type.is_active)
                      .map((type) => (
                        <option key={type.id} value={type.id}>
                          {type.name}
                        </option>
                      ))}
                  </Select>
                  {types.isPending ? (
                    <p role="status" className="mt-2 text-sm text-muted">
                      Loading assessment types…
                    </p>
                  ) : types.isError ? (
                    <p role="alert" className="mt-2 text-sm text-danger">
                      Assessment Types could not be loaded.{" "}
                      <Button
                        type="button"
                        variant="quiet"
                        onClick={() => void types.refetch()}
                      >
                        Retry types
                      </Button>
                    </p>
                  ) : catalog?.every((type) => !type.is_active) ? (
                    <p className="mt-2 text-sm text-muted">
                      No active Assessment Types. Ask Head Guidance to configure
                      the catalog.
                    </p>
                  ) : null}
                </div>
                <div>
                  <Label htmlFor="assessment-administered">
                    Administered on
                  </Label>
                  <Input
                    id="assessment-administered"
                    type="date"
                    required
                    max={institutionalDateInputValue()}
                    value={draft.administered_on}
                    onChange={(event) =>
                      field("administered_on", event.target.value)
                    }
                  />
                </div>
              </div>
            </PanelSection>
            <PanelSection
              title="Assessment result"
              titleId="assessment-form-content"
              description="Confidential. Enter the source text, including a score or rating exactly as supplied. At least one result field is required."
            >
              <div className="space-y-5">
                {assessmentContentFields.map((item) => (
                  <div key={item.key}>
                    <Label htmlFor={`assessment-${item.key}`}>
                      {item.label}
                    </Label>
                    <Textarea
                      id={`assessment-${item.key}`}
                      rows={item.key === "score" ? 2 : 4}
                      maxLength={item.maximum}
                      autoComplete="off"
                      value={draft[item.key]}
                      onChange={(event) => field(item.key, event.target.value)}
                      aria-describedby={
                        item.key === "score"
                          ? "assessment-score-help"
                          : undefined
                      }
                    />
                    {item.key === "score" ? (
                      <p
                        id="assessment-score-help"
                        className="mt-1 text-xs text-muted"
                      >
                        Text, such as “88/100”, “High” or the source rating.
                        COMPASS does not calculate scores.
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </PanelSection>
          </fieldset>
          {error ? (
            <div className="px-4 pb-4 sm:px-5">
              <Notice role="alert" tone="danger">
                {error}
              </Notice>
            </div>
          ) : null}
          <PanelFooter>
            <Button
              type="submit"
              disabled={pending || !catalog || types.isError}
            >
              {pending
                ? "Saving…"
                : record
                  ? "Save corrections"
                  : "Save record"}
            </Button>
            <Link href={back} className={buttonVariants({ variant: "quiet" })}>
              Cancel
            </Link>
          </PanelFooter>
        </form>
      </Panel>
    </>
  );
}
