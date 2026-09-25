import type { ReactNode } from "react";
import Link from "next/link";

import type { ExitInterviewDetailResponse } from "@/lib/api/generated/model";
import {
  DELAY_REASONS,
  SELF_ASSESSMENT_ITEMS,
  SELF_ASSESSMENT_SCALE,
  COLLEGE_FEEDBACK_CATEGORIES,
  COLLEGE_FEEDBACK_SCALE,
  CAREER_MODES,
  SIGNIFICANT_LEARNING_CHOICES,
  STUDY_CHOICES,
  WORK_CHOICES,
  formatExitInterviewDateTime,
} from "@/features/exit-interviews/exit-interview-presentation";
import {
  ExitInterviewField,
  ExitInterviewHeading,
  ExitInterviewSection,
  ExitInterviewStatus,
} from "@/features/exit-interviews/exit-interview-shared";
import { ExitInterviewCorrectionHistory } from "@/features/exit-interviews/exit-interview-correction-history";

function choiceLabels<T extends string>(
  selected: readonly T[] | undefined,
  choices: readonly { value: T; label: string }[],
): string {
  const labels = choices
    .filter((choice) => selected?.includes(choice.value))
    .map((choice) => choice.label);
  return labels.length ? labels.join(", ") : "Not provided";
}

function RatingTable({
  caption,
  rows,
  legend,
  renderValue,
}: {
  caption: string;
  rows: readonly { code: string; label: string; value: number | undefined }[];
  legend: ReactNode;
  renderValue: (value: number | undefined) => string;
}) {
  return (
    <>
      <p className="mt-3 text-sm leading-6 text-muted">{legend}</p>
      <div className="mt-3 overflow-x-auto rounded-md border border-border">
        <table className="min-w-[34rem] w-full border-collapse text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface-muted text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="sticky left-0 z-10 min-w-64 bg-surface-muted px-3 py-3 font-semibold">Item</th>
              <th scope="col" className="px-3 py-3 font-semibold">Response</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row) => (
              <tr key={row.code}>
                <th scope="row" className="sticky left-0 z-10 bg-surface-raised px-3 py-3 text-left font-medium text-ink">{row.label}</th>
                <td className="px-3 py-3 text-ink">{renderValue(row.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function ExitInterviewResponse({
  detail,
  studentFacing,
  backHref,
  headerAction,
}: {
  detail: ExitInterviewDetailResponse;
  studentFacing: boolean;
  backHref: string;
  headerAction?: ReactNode;
}) {
  const selfRatings = new Map(
    detail.self_assessment_ratings.map((rating) => [rating.item_code, rating]),
  );
  const feedbackRatings = new Map(
    detail.college_feedback_ratings.map((rating) => [rating.item_code, rating]),
  );
  const collegeRatingByCode = new Map(
    COLLEGE_FEEDBACK_CATEGORIES.flatMap((category) =>
      category.items.map((item) => [item.code, feedbackRatings.get(item.code)] as const),
    ),
  );
  return (
    <section className="space-y-2">
      <Link
        href={backHref}
        className="inline-flex min-h-9 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        {studentFacing ? "Back to Exit Interviews" : "Back to Exit Interview queue"}
      </Link>
      <ExitInterviewHeading
        title={studentFacing ? "Exit Interview" : detail.student_name || detail.student.display_name}
        description={studentFacing ? detail.academic_year.label : `${detail.academic_year.label}${detail.student.institutional_id ? ` · ${detail.student.institutional_id}` : ""}`}
        action={
          <div className="flex flex-wrap items-center gap-3">
            <ExitInterviewStatus status={detail.status} />
            {headerAction}
          </div>
        }
      />

      <section aria-labelledby="exit-interview-record-facts" className="py-5">
        <h2 id="exit-interview-record-facts" className="sr-only">Exit Interview record facts</h2>
        <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          <ExitInterviewField label="Academic Year" value={detail.academic_year.label} />
          <ExitInterviewField label="Status" value={detail.status === "DRAFT" ? "Draft" : "Submitted"} />
          <ExitInterviewField label="First submitted" value={formatExitInterviewDateTime(detail.first_submitted_at)} />
          <ExitInterviewField label="Last submitted" value={formatExitInterviewDateTime(detail.last_submitted_at)} />
          <ExitInterviewField label="Updated" value={formatExitInterviewDateTime(detail.updated_at)} />
          {!studentFacing ? <ExitInterviewField label="Student" value={detail.student_name || detail.student.display_name} /> : null}
        </dl>
      </section>

      <ExitInterviewSection title="General information" id="exit-interview-general-information">
        <dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">
          <ExitInterviewField label="Student name" value={detail.student_name} />
          <ExitInterviewField label="Age" value={detail.age === null || detail.age === undefined ? null : String(detail.age)} />
          <ExitInterviewField label="Civil Status" value={detail.civil_status} />
          <ExitInterviewField label="Course" value={detail.course} />
          <ExitInterviewField label="Major" value={detail.major} />
          <ExitInterviewField label="Email Address" value={detail.email_address} />
          <ExitInterviewField label="Contact Number" value={detail.contact_number} />
          <ExitInterviewField label="Home Address" value={detail.home_address} />
        </dl>
      </ExitInterviewSection>

      <ExitInterviewSection title="Section I — Program completion and plans" id="exit-interview-program-completion">
        <dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">
          <ExitInterviewField
            label="Program completion"
            value={detail.program_completion === "ACCORDING_TO_SCHEDULE" ? "According to schedule" : detail.program_completion === "WITH_SOME_DELAY" ? "With some delay" : null}
          />
          {detail.program_completion === "WITH_SOME_DELAY" ? (
            <>
              <ExitInterviewField label="Number of extra terms" value={detail.extra_terms_count === null || detail.extra_terms_count === undefined ? null : String(detail.extra_terms_count)} />
              <ExitInterviewField label="Reason for delay" value={choiceLabels(detail.delay_reasons, DELAY_REASONS)} />
              {detail.delay_reasons?.includes("OTHER") ? <ExitInterviewField label="Other delay reason" value={detail.delay_other} /> : null}
            </>
          ) : null}
          <ExitInterviewField label="Significant learning experiences" value={choiceLabels(detail.significant_learning_experiences, SIGNIFICANT_LEARNING_CHOICES)} />
          {detail.significant_learning_experiences?.includes("OTHER") ? <ExitInterviewField label="Other learning experience" value={detail.significant_learning_other} /> : null}
          <ExitInterviewField label="Career modes" value={choiceLabels(detail.career_modes, CAREER_MODES)} />
          {detail.career_modes?.includes("WORK") ? <ExitInterviewField label="Work plans" value={choiceLabels(detail.work_choices, WORK_CHOICES)} /> : null}
          {detail.career_modes?.includes("STUDY") ? <ExitInterviewField label="Study plans" value={choiceLabels(detail.study_choices, STUDY_CHOICES)} /> : null}
        </dl>
      </ExitInterviewSection>

      <ExitInterviewSection title="Section II — Self-Assessment" id="exit-interview-self-assessment">
        <RatingTable
          caption="Self-Assessment ratings"
          rows={SELF_ASSESSMENT_ITEMS.map((item) => ({
            code: item.code,
            label: selfRatings.get(item.code)?.item_label ?? item.label,
            value: selfRatings.get(item.code)?.rating,
          }))}
          legend={<>5 — Much enhanced; 4 — Enhanced; 3 — No Difference; 2 — Became Worse; 1 — I don&apos;t know.</>}
          renderValue={(value) => value === undefined ? "Not answered" : SELF_ASSESSMENT_SCALE.find((item) => item.value === value)?.label ?? String(value)}
        />
      </ExitInterviewSection>

      <ExitInterviewSection title="Section III — College Feedback" id="exit-interview-college-feedback">
        <p className="mt-2 text-sm leading-6 text-muted">5 — Highly Satisfactory; 4 — Satisfactory; 3 — Average; 2 — Unsatisfactory; 1 — Very Unsatisfactory.</p>
        <p className="mt-2 text-sm text-muted">The source form includes 0 as a response option but does not specify its meaning.</p>
        {COLLEGE_FEEDBACK_CATEGORIES.map((category) => {
          const comment = detail[category.commentField];
          return (
            <section key={category.code} aria-labelledby={`exit-response-${category.code.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} className="mt-6 border-t border-border pt-5">
              <h3 id={`exit-response-${category.code.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} className="font-semibold text-ink">{category.label}</h3>
              <RatingTable
                caption={`${category.label} feedback ratings`}
                rows={category.items.map((item) => {
                  const rating = collegeRatingByCode.get(item.code);
                  const canonicalLabel = rating?.item_label.split(" — ").slice(1).join(" — ");
                  return { code: item.code, label: canonicalLabel || rating?.item_label || item.label, value: rating?.rating };
                })}
                legend={<>0 is shown as a numeric response only. 5 — Highly Satisfactory; 4 — Satisfactory; 3 — Average; 2 — Unsatisfactory; 1 — Very Unsatisfactory.</>}
                renderValue={(value) => value === undefined ? "Not answered" : value === 0 ? "0" : COLLEGE_FEEDBACK_SCALE.find((item) => item.value === value)?.label ?? String(value)}
              />
              <div className="mt-4 max-w-3xl">
                <dl>
                  <ExitInterviewField label={category.commentLabel} value={comment} />
                </dl>
              </div>
            </section>
          );
        })}
      </ExitInterviewSection>

      <ExitInterviewSection title="Suggestions / Recommendations" id="exit-interview-suggestions">
        <div className="mt-4 max-w-3xl">
          <ExitInterviewField label="Suggestions / Recommendations" value={detail.suggestions_recommendations} />
        </div>
      </ExitInterviewSection>

      {detail.reopen_events.length ? (
        <ExitInterviewCorrectionHistory
          events={detail.reopen_events}
          emphasizeLatest={studentFacing && detail.status === "DRAFT"}
        />
      ) : null}
    </section>
  );
}
