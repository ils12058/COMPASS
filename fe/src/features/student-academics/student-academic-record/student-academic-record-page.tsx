"use client";

import { useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Plus } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button } from "@/components/ui/button";
import {
  ConsequentialActionDialog,
  type ConsequentialActionCompletion,
} from "@/components/ui/consequential-action-dialog";
import { dataTable } from "@/components/ui/data-table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass, PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useOrganizationAction } from "@/features/organization/components/organization-action";
import {
  QueryError,
  StatusBadge,
  TableSkeleton,
} from "@/features/organization/components/organization-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getStudentAcademicsGetStudentRecordQueryKey,
  getStudentAcademicsListPlacementsQueryKey,
  useStudentAcademicsGetStudentRecord,
  useStudentAcademicsRecordGraduation,
  useStudentAcademicsRecordPeriod,
} from "@/lib/api/generated/student-academics/student-academics";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import { useOrganizationListColleges } from "@/lib/api/generated/organization/organization";
import {
  AcademicTerm,
  EnrollmentStatus,
} from "@/lib/api/generated/model";
import type {
  AcademicPeriodRecordResponse,
  CollegeSummary,
  PlacementVerificationStatus,
  StudentLifecycleStatus,
} from "@/lib/api/generated/model";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";

import {
  academicTermLabel,
  enrollmentStatusLabel,
  lifecycleStatusLabel,
  yearLevelLabel,
} from "./academic-record-presentation";

const LIST_PATH = "/portal/organization/student-academics";

type PeriodForm = {
  academicYearId: string;
  term: AcademicTerm | "";
  collegeId: string;
  yearLevel: string;
  enrollmentStatus: EnrollmentStatus;
};

type GraduationForm = {
  graduationDate: string;
  collegeId: string;
  verificationSource: string;
};

type GraduationReview = {
  form: GraduationForm;
  college: CollegeSummary;
  updating: boolean;
};

function RecordFact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-ink [overflow-wrap:anywhere]">
        {children}
      </dd>
    </div>
  );
}

function LifecycleBadge({ status }: { status: StudentLifecycleStatus | null }) {
  return (
    <span className="inline-flex rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted">
      {lifecycleStatusLabel(status)}
    </span>
  );
}

function VerificationBadge({
  status,
}: {
  status: PlacementVerificationStatus;
}) {
  return (
    <span className="inline-flex rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted">
      {status === "VERIFIED" ? "Verified" : "Unverified"}
    </span>
  );
}

export function StudentAcademicRecordPage({ studentId }: { studentId: string }) {
  const { user } = usePortalSession();
  const canViewStructure = user.capabilities.includes("organization.structure.view");
  const canViewAcademicYears = user.capabilities.includes("academic_years.view");
  const queryClient = useQueryClient();
  const action = useOrganizationAction();
  const status = useActionStatus();

  const record = useStudentAcademicsGetStudentRecord(studentId, {
    query: { retry: false },
  });
  const colleges = useOrganizationListColleges(
    {},
    { query: { enabled: canViewStructure, retry: false } },
  );
  const academicYears = useAcademicYearsList({
    query: { enabled: canViewAcademicYears, retry: false },
  });
  const recordPeriod = useStudentAcademicsRecordPeriod();
  const recordGraduation = useStudentAcademicsRecordGraduation();

  const [periodForm, setPeriodForm] = useState<PeriodForm | null>(null);
  const [periodEditing, setPeriodEditing] = useState(false);
  const [graduationForm, setGraduationForm] = useState<GraduationForm | null>(null);
  const [graduationReview, setGraduationReview] =
    useState<GraduationReview | null>(null);
  const [graduationCompleted, setGraduationCompleted] =
    useState<ConsequentialActionCompletion | null>(null);

  const structureUnavailable = !canViewStructure || colleges.isError;
  const structureReady = canViewStructure && Boolean(colleges.data);
  const yearsUnavailable = !canViewAcademicYears || academicYears.isError;
  const yearsReady = canViewAcademicYears && Boolean(academicYears.data);
  const periodFormReady = structureReady && yearsReady;
  const graduationFormReady = structureReady;

  const activeColleges =
    colleges.data?.data.items.filter(
      (college) => college.is_active && college.campus.is_active,
    ) ?? [];
  const academicYearItems = academicYears.data?.data.items ?? [];

  const yearLevelValue = periodForm?.yearLevel.trim() ?? "";
  const parsedYearLevel =
    yearLevelValue === "" ? null : Number(yearLevelValue);
  const yearLevelInvalid =
    parsedYearLevel !== null &&
    (!Number.isInteger(parsedYearLevel) ||
      parsedYearLevel < 1 ||
      parsedYearLevel > 8);

  function resetActionFeedback() {
    action.setError(null);
    action.setNotice(null);
  }

  function openBlankPeriod() {
    resetActionFeedback();
    setPeriodEditing(false);
    setPeriodForm({
      academicYearId: "",
      term: "",
      collegeId: "",
      yearLevel: "",
      enrollmentStatus: EnrollmentStatus.UNKNOWN,
    });
  }

  function openPeriodUpdate(item: AcademicPeriodRecordResponse) {
    resetActionFeedback();
    setPeriodEditing(true);
    setPeriodForm({
      academicYearId: item.academic_year.id,
      term: item.term,
      collegeId: item.college.id,
      yearLevel: item.year_level === null ? "" : String(item.year_level),
      enrollmentStatus: item.enrollment_status,
    });
  }

  function openGraduationForm() {
    resetActionFeedback();
    const graduation = record.data?.data.graduation;
    setGraduationForm(
      graduation
        ? {
            graduationDate: graduation.graduation_date,
            collegeId: graduation.graduated_college.id,
            verificationSource: graduation.verification_source,
          }
        : { graduationDate: "", collegeId: "", verificationSource: "" },
    );
  }

  async function savePeriod() {
    if (!periodForm || !periodForm.term) return;
    const form = periodForm;
    const response = await action.run(
      () =>
        recordPeriod.mutateAsync({
          studentId,
          data: {
            academic_year_id: form.academicYearId,
            term: form.term as AcademicTerm,
            college_id: form.collegeId,
            year_level: parsedYearLevel,
            enrollment_status: form.enrollmentStatus,
          },
        }),
      "The academic period could not be recorded.",
    );
    if (!response) return;
    setPeriodForm(null);
    status.show("Academic period recorded.");
    await queryClient.invalidateQueries({
      queryKey: getStudentAcademicsGetStudentRecordQueryKey(studentId),
    });
  }

  function reviewGraduation() {
    if (!graduationForm) return;
    const college = activeColleges.find(
      (item) => item.id === graduationForm.collegeId,
    );
    if (!college) return;
    resetActionFeedback();
    setGraduationReview({
      form: graduationForm,
      college,
      updating: Boolean(record.data?.data.graduation),
    });
    setGraduationForm(null);
    setGraduationCompleted(null);
  }

  async function saveGraduation() {
    if (!graduationReview) return;
    const review = graduationReview;
    const studentName = record.data?.data.student.full_name ?? "The Student";
    const response = await action.run(
      () =>
        recordGraduation.mutateAsync({
          studentId,
          data: {
            graduated_college_id: review.form.collegeId,
            graduation_date: review.form.graduationDate,
            verification_source: review.form.verificationSource.trim(),
          },
        }),
      "The graduation record could not be saved.",
    );
    if (!response) return;
    setGraduationCompleted({
      title: review.updating ? "Graduation updated." : "Graduation recorded.",
      children: (
        <>
          <p>
            {studentName} is recorded as graduated from {review.college.name} on{" "}
            {formatDateOnly(review.form.graduationDate)}.
          </p>
          <p>
            The current placement is cleared and the Student lifecycle is
            Graduated. Exit Interview and Good Moral were not checked or changed.
          </p>
        </>
      ),
    });
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getStudentAcademicsGetStudentRecordQueryKey(studentId),
      }),
      queryClient.invalidateQueries({
        queryKey: getStudentAcademicsListPlacementsQueryKey(),
      }),
    ]);
  }

  const back = (
    <Link href={LIST_PATH} className={pageBackLinkClass}>
      Back to Student placements
    </Link>
  );

  if (record.isPending) {
    return (
      <section aria-labelledby="student-academic-record-heading">
        <PageHeader
          title="Student academic record"
          headingId="student-academic-record-heading"
          back={back}
        />
        <TableSkeleton label="Loading Student academic record…" />
      </section>
    );
  }

  if (record.isError && !record.data) {
    return (
      <section aria-labelledby="student-academic-record-heading">
        <PageHeader
          title="Student academic record"
          headingId="student-academic-record-heading"
          back={back}
        />
        <QueryError
          error={record.error}
          fallback="The Student academic record could not be loaded."
          onRetry={() => void record.refetch()}
        />
      </section>
    );
  }

  const data = record.data.data;

  return (
    <section aria-labelledby="student-academic-record-heading">
      <PageHeader
        title={data.student.full_name}
        headingId="student-academic-record-heading"
        back={back}
        context="Student academic record"
        description={
          data.student.institutional_id
            ? `Institutional ID ${data.student.institutional_id} · ${data.student.email}`
            : data.student.email
        }
        meta={
          <span className="flex flex-wrap items-center gap-2">
            <LifecycleBadge status={data.lifecycle_status} />
            <StatusBadge active={data.student.is_active} />
          </span>
        }
      />

      {structureUnavailable ? (
        <Notice role="status" tone="warning" className="mb-5">
          Organization structure is unavailable to this account, so College choices
          cannot be loaded. Period and graduation forms are unavailable; recorded
          facts remain visible.
        </Notice>
      ) : null}

      <Panel aria-labelledby="current-placement-heading" className="mb-5">
        <PanelHeader
          title="Current placement"
          titleId="current-placement-heading"
        />
        {data.placement ? (
          <div className="px-4 py-4 sm:px-5">
            <dl className="grid gap-4 sm:grid-cols-2">
              <RecordFact label="College">
                {data.placement.college.name}
              </RecordFact>
              <RecordFact label="Campus">
                {data.placement.college.campus.name}
              </RecordFact>
              <RecordFact label="Verification">
                <VerificationBadge
                  status={data.placement.verification_status}
                />
              </RecordFact>
              <RecordFact label="Program">
                No Program is recorded. Placement is College-only.
              </RecordFact>
            </dl>
            <p className="mt-4 text-sm leading-6 text-muted">
              Placement changes are made in Student placements.
            </p>
          </div>
        ) : (
          <PanelMessage>No current College placement.</PanelMessage>
        )}
      </Panel>

      <Panel aria-labelledby="academic-periods-heading" className="mb-5">
        <PanelHeader
          title="Academic periods"
          titleId="academic-periods-heading"
          context={
            data.periods.length === 1
              ? "1 recorded"
              : `${data.periods.length} recorded`
          }
          actions={
            <Button
              variant="secondary"
              disabled={!periodFormReady}
              onClick={openBlankPeriod}
            >
              <Plus size={16} aria-hidden="true" />
              Record period
            </Button>
          }
        />
        {yearsUnavailable ? (
          <Notice role="status" tone="warning" className="mx-4 my-4 sm:mx-5">
            Academic Years are unavailable to this account, so academic periods
            cannot be recorded.
          </Notice>
        ) : null}
        {data.periods.length === 0 ? (
          <PanelMessage>No academic periods recorded.</PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[48rem]`}>
              <caption className="sr-only">Academic periods</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th
                    scope="col"
                    className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}
                  >
                    Academic year
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Term
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    College
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Year level
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Enrollment
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Last updated
                  </th>
                  <th
                    scope="col"
                    className={`${dataTable.headerCell} text-right`}
                  >
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {data.periods.map((item) => (
                  <tr key={item.id} className={dataTable.row}>
                    <th
                      scope="row"
                      className={`${dataTable.cell} ${dataTable.stickyCell} font-normal text-ink`}
                    >
                      {item.academic_year.label}
                    </th>
                    <td className={dataTable.cell}>
                      {academicTermLabel(item.term)}
                    </td>
                    <td className={dataTable.cell}>{item.college.name}</td>
                    <td className={dataTable.cell}>
                      {yearLevelLabel(item.year_level)}
                    </td>
                    <td className={dataTable.cell}>
                      {enrollmentStatusLabel(item.enrollment_status)}
                    </td>
                    <td className={dataTable.cell}>
                      {formatInstitutionalDateTime(item.updated_at)}
                    </td>
                    <td className={`${dataTable.cell} py-2`}>
                      <div className="flex justify-end">
                        <Button
                          variant="quiet"
                          disabled={!periodFormReady}
                          onClick={() => openPeriodUpdate(item)}
                        >
                          Update
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel aria-labelledby="graduation-heading">
        <PanelHeader
          title="Graduation"
          titleId="graduation-heading"
          actions={
            <Button
              variant="secondary"
              disabled={!graduationFormReady}
              onClick={openGraduationForm}
            >
              <GraduationCap size={16} aria-hidden="true" />
              {data.graduation ? "Update graduation" : "Record graduation"}
            </Button>
          }
        />
        {data.graduation ? (
          <div className="px-4 py-4 sm:px-5">
            <dl className="grid gap-4 sm:grid-cols-2">
              <RecordFact label="College">
                {data.graduation.graduated_college.name}
              </RecordFact>
              <RecordFact label="Graduation date">
                {formatDateOnly(data.graduation.graduation_date)}
              </RecordFact>
              <RecordFact label="Verification source">
                {data.graduation.verification_source}
              </RecordFact>
              <RecordFact label="Verified by">
                {data.graduation.verified_by?.full_name ?? "Not recorded"}
              </RecordFact>
              <RecordFact label="Verified at">
                {formatInstitutionalDateTime(data.graduation.verified_at)}
              </RecordFact>
              <RecordFact label="Last updated">
                {formatInstitutionalDateTime(data.graduation.updated_at)}
              </RecordFact>
            </dl>
          </div>
        ) : (
          <PanelMessage>No graduation recorded.</PanelMessage>
        )}
      </Panel>

      <Dialog
        open={periodForm !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPeriodForm(null);
            resetActionFeedback();
          }
        }}
      >
        <DialogContent
          className="max-w-xl"
          dismissible={!recordPeriod.isPending}
        >
          <DialogTitle>
            {periodEditing ? "Update academic period" : "Record academic period"}
          </DialogTitle>
          <DialogDescription>
            {periodEditing
              ? "Update the history record for this Academic Year and term."
              : "Record the Student's College, year level, and enrollment classification for one Academic Year and term."}
          </DialogDescription>
          {periodForm ? (
            <div className="mt-6 space-y-5">
              <div>
                <Label htmlFor="record-period-academic-year">
                  Academic year
                </Label>
                <Select
                  id="record-period-academic-year"
                  className="mt-2"
                  required
                  value={periodForm.academicYearId}
                  onChange={(event) =>
                    setPeriodForm({
                      ...periodForm,
                      academicYearId: event.target.value,
                    })
                  }
                >
                  <option value="">Select Academic year</option>
                  {academicYearItems.map((year) => (
                    <option key={year.id} value={year.id}>
                      {year.label}
                      {year.is_current ? " (current)" : ""}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="record-period-term">Term</Label>
                <Select
                  id="record-period-term"
                  className="mt-2"
                  required
                  value={periodForm.term}
                  onChange={(event) =>
                    setPeriodForm({
                      ...periodForm,
                      term: event.target.value as AcademicTerm | "",
                    })
                  }
                >
                  <option value="">Select term</option>
                  {Object.values(AcademicTerm).map((term) => (
                    <option key={term} value={term}>
                      {academicTermLabel(term)}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="record-period-college">College</Label>
                <Select
                  id="record-period-college"
                  className="mt-2"
                  required
                  value={periodForm.collegeId}
                  onChange={(event) =>
                    setPeriodForm({
                      ...periodForm,
                      collegeId: event.target.value,
                    })
                  }
                >
                  <option value="">Select College</option>
                  {activeColleges.map((college) => (
                    <option key={college.id} value={college.id}>
                      {college.code} — {college.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="record-period-year-level">
                  Year level (optional)
                </Label>
                <Input
                  id="record-period-year-level"
                  className="mt-2"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={8}
                  step={1}
                  value={periodForm.yearLevel}
                  aria-invalid={yearLevelInvalid}
                  onChange={(event) =>
                    setPeriodForm({
                      ...periodForm,
                      yearLevel: event.target.value,
                    })
                  }
                />
                {yearLevelInvalid ? (
                  <p role="alert" className="mt-2 text-sm text-danger">
                    Year level must be a whole number from 1 to 8.
                  </p>
                ) : null}
              </div>
              <div>
                <Label htmlFor="record-period-enrollment">
                  Enrollment status
                </Label>
                <Select
                  id="record-period-enrollment"
                  className="mt-2"
                  value={periodForm.enrollmentStatus}
                  onChange={(event) =>
                    setPeriodForm({
                      ...periodForm,
                      enrollmentStatus: event.target.value as EnrollmentStatus,
                    })
                  }
                >
                  {Object.values(EnrollmentStatus).map((enrollment) => (
                    <option key={enrollment} value={enrollment}>
                      {enrollmentStatusLabel(enrollment)}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          ) : null}
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={recordPeriod.isPending}
              onClick={() => setPeriodForm(null)}
            >
              Cancel
            </Button>
            <Button
              disabled={
                recordPeriod.isPending ||
                !periodForm ||
                !periodForm.academicYearId ||
                !periodForm.term ||
                !periodForm.collegeId ||
                yearLevelInvalid
              }
              onClick={() => void savePeriod()}
            >
              {recordPeriod.isPending ? "Saving…" : "Save period"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={graduationForm !== null}
        onOpenChange={(open) => {
          if (!open) {
            setGraduationForm(null);
            resetActionFeedback();
          }
        }}
      >
        <DialogContent
          className="max-w-xl"
          dismissible={!recordGraduation.isPending}
        >
          <DialogTitle>
            {data.graduation ? "Update graduation" : "Record graduation"}
          </DialogTitle>
          <DialogDescription>
            Record the confirmed graduation. The consequences are repeated before
            the change is saved.
          </DialogDescription>
          {graduationForm ? (
            <div className="mt-6 space-y-5">
              <div>
                <Label htmlFor="record-graduation-date">Graduation date</Label>
                <Input
                  id="record-graduation-date"
                  className="mt-2"
                  type="date"
                  required
                  value={graduationForm.graduationDate}
                  onChange={(event) =>
                    setGraduationForm({
                      ...graduationForm,
                      graduationDate: event.target.value,
                    })
                  }
                />
              </div>
              <div>
                <Label htmlFor="record-graduation-college">College</Label>
                <Select
                  id="record-graduation-college"
                  className="mt-2"
                  required
                  value={graduationForm.collegeId}
                  onChange={(event) =>
                    setGraduationForm({
                      ...graduationForm,
                      collegeId: event.target.value,
                    })
                  }
                >
                  <option value="">Select College</option>
                  {activeColleges.map((college) => (
                    <option key={college.id} value={college.id}>
                      {college.code} — {college.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="record-graduation-source">
                  Verification source
                </Label>
                <Textarea
                  id="record-graduation-source"
                  className="mt-2"
                  required
                  maxLength={200}
                  value={graduationForm.verificationSource}
                  onChange={(event) =>
                    setGraduationForm({
                      ...graduationForm,
                      verificationSource: event.target.value,
                    })
                  }
                />
                <p className="mt-1 text-xs leading-5 text-muted">
                  Where the graduation was confirmed. Up to 200 characters.
                </p>
              </div>
            </div>
          ) : null}
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={recordGraduation.isPending}
              onClick={() => setGraduationForm(null)}
            >
              Cancel
            </Button>
            <Button
              disabled={
                recordGraduation.isPending ||
                !graduationForm ||
                !graduationForm.graduationDate ||
                !graduationForm.collegeId ||
                !graduationForm.verificationSource.trim()
              }
              onClick={reviewGraduation}
            >
              Review graduation
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConsequentialActionDialog
        open={graduationReview !== null}
        title={
          graduationReview?.updating
            ? "Update graduation record?"
            : "Record graduation?"
        }
        confirmLabel={
          graduationReview?.updating ? "Update graduation" : "Record graduation"
        }
        pendingLabel={graduationReview?.updating ? "Updating…" : "Recording…"}
        pending={recordGraduation.isPending}
        error={action.error}
        completed={graduationCompleted}
        onOpenChange={(open) => {
          if (!open) {
            setGraduationReview(null);
            setGraduationCompleted(null);
            resetActionFeedback();
          }
        }}
        onConfirm={() => void saveGraduation()}
      >
        {graduationReview ? (
          <>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-muted">Student</dt>
                <dd className="font-semibold text-ink">
                  {data.student.full_name}
                </dd>
              </div>
              <div>
                <dt className="text-muted">College</dt>
                <dd className="font-semibold text-ink">
                  {graduationReview.college.name}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Graduation date</dt>
                <dd className="font-semibold text-ink">
                  {formatDateOnly(graduationReview.form.graduationDate)}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Current placement</dt>
                <dd className="font-semibold text-ink">
                  {data.placement ? "Will be cleared" : "No current placement"}
                </dd>
              </div>
            </dl>
            <p>
              {graduationReview.updating ? "Updating graduation" : "Recording graduation"}{" "}
              clears the current placement and sets the Student lifecycle to
              Graduated. Exit Interview and Good Moral are not checked or changed.
            </p>
          </>
        ) : null}
      </ConsequentialActionDialog>

      {action.stepUpDialog}
      <ActionStatus status={status.status} onDismiss={status.dismiss} />
    </section>
  );
}
