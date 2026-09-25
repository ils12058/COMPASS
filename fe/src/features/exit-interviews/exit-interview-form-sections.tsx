import type {
  CareerModeValue,
  DelayReasonValue,
  ProgramCompletionValue,
  SignificantLearningValue,
  StudyCareerChoiceValue,
  WorkCareerChoiceValue,
} from "@/lib/api/generated/model";
import {
  CareerModeValue as CareerMode,
  DelayReasonValue as DelayReason,
  ProgramCompletionValue as ProgramCompletion,
  SignificantLearningValue as SignificantLearning,
} from "@/lib/api/generated/model";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  COLLEGE_FEEDBACK_CATEGORIES,
  COLLEGE_FEEDBACK_SCALE,
  DELAY_REASONS,
  SELF_ASSESSMENT_ITEMS,
  SELF_ASSESSMENT_SCALE,
  SIGNIFICANT_LEARNING_CHOICES,
  STUDY_CHOICES,
  WORK_CHOICES,
  type ExitInterviewFormState,
} from "@/features/exit-interviews/exit-interview-presentation";
import { ExitInterviewSection } from "@/features/exit-interviews/exit-interview-shared";

const PROGRAM_COMPLETION_CHOICES: readonly {
  value: ProgramCompletionValue;
  label: string;
}[] = [
  { value: ProgramCompletion.ACCORDING_TO_SCHEDULE, label: "According to schedule" },
  { value: ProgramCompletion.WITH_SOME_DELAY, label: "With some delay" },
];

export type ExitInterviewTextFieldKey =
  | "studentName"
  | "age"
  | "civilStatus"
  | "course"
  | "major"
  | "emailAddress"
  | "homeAddress"
  | "contactNumber"
  | "extraTermsCount"
  | "delayOther"
  | "significantLearningOther"
  | "deanComments"
  | "programChairComments"
  | "facultyComments"
  | "curriculumComments"
  | "guidanceCounselorComments"
  | "officeStaffComments"
  | "facilitiesComments"
  | "suggestionsRecommendations";

type RatingItem = { code: string; label: string };
type RatingScale = readonly { value: number; label: string }[];

function FormField({
  id,
  label,
  value,
  disabled,
  onChange,
  type = "text",
  min,
  max,
  required = false,
}: {
  id: string;
  label: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  type?: "text" | "email" | "number" | "tel";
  min?: number;
  max?: number;
  required?: boolean;
}) {
  return (
    <div className="min-w-0">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        className="mt-2"
        type={type}
        value={value}
        min={min}
        max={max}
        step={type === "number" ? 1 : undefined}
        required={required}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function FormTextArea({
  id,
  label,
  value,
  disabled,
  onChange,
  required = false,
}: {
  id: string;
  label: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <div className="min-w-0">
      <Label htmlFor={id}>{label}</Label>
      <Textarea
        id={id}
        className="mt-2 min-h-24"
        value={value}
        required={required}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function ChoiceCheckbox({
  id,
  label,
  checked,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label htmlFor={id} className="flex min-h-9 items-center gap-2 text-sm text-ink">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 shrink-0 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      />
      <span>{label}</span>
    </label>
  );
}

function RatingMatrix({
  title,
  items,
  values,
  scale,
  zeroChoice = false,
  disabled,
  onChange,
}: {
  title: string;
  items: readonly RatingItem[];
  values: Record<string, string>;
  scale: RatingScale;
  zeroChoice?: boolean;
  disabled: boolean;
  onChange: (code: string, value: string) => void;
}) {
  const options = zeroChoice
    ? [{ value: 0, label: "" }, ...scale.slice().reverse()]
    : scale;

  return (
    <div className="mt-4 overflow-x-auto rounded-md border border-border">
      <table className="min-w-[42rem] w-full border-collapse text-sm">
        <caption className="sr-only">{title} rating matrix</caption>
        <thead className="bg-surface-muted text-xs text-muted">
          <tr>
            <th scope="col" className="sticky left-0 z-10 min-w-64 bg-surface-muted px-3 py-3 text-left font-semibold">
              Item
            </th>
            {options.map((option) => (
              <th key={option.value} scope="col" className="min-w-16 px-2 py-3 text-center font-semibold">
                <span>{option.value}</span>
                {option.label ? <span className="sr-only"> — {option.label}</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item) => (
            <tr key={item.code} className="align-middle">
              <th scope="row" className="sticky left-0 z-10 bg-surface-raised px-3 py-3 text-left font-medium text-ink">
                {item.label}
              </th>
              {options.map((option) => {
                const id = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${item.code}-${option.value}`;
                const accessibleValue = option.label
                  ? `${option.value}, ${option.label}`
                  : String(option.value);
                return (
                  <td key={option.value} className="px-2 py-3 text-center">
                    <label htmlFor={id} className="inline-flex min-h-8 min-w-8 cursor-pointer items-center justify-center rounded focus-within:outline-none focus-within:ring-2 focus-within:ring-focus">
                      <input
                        id={id}
                        type="radio"
                        name={`${title}-${item.code}`}
                        value={option.value}
                        checked={values[item.code] === String(option.value)}
                        disabled={disabled}
                        onChange={() => onChange(item.code, String(option.value))}
                        className="h-4 w-4 accent-brand"
                      />
                      <span className="sr-only">{item.label}: {accessibleValue}</span>
                    </label>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ExitInterviewFormSections({
  form,
  disabled,
  onTextChange,
  onProgramCompletionChange,
  onToggleDelayReason,
  onToggleLearning,
  onToggleCareerMode,
  onToggleWorkChoice,
  onToggleStudyChoice,
  onRatingChange,
}: {
  form: ExitInterviewFormState;
  disabled: boolean;
  onTextChange: (field: ExitInterviewTextFieldKey, value: string) => void;
  onProgramCompletionChange: (value: "" | ProgramCompletionValue) => void;
  onToggleDelayReason: (value: DelayReasonValue) => void;
  onToggleLearning: (value: SignificantLearningValue) => void;
  onToggleCareerMode: (value: CareerModeValue) => void;
  onToggleWorkChoice: (value: WorkCareerChoiceValue) => void;
  onToggleStudyChoice: (value: StudyCareerChoiceValue) => void;
  onRatingChange: (section: "selfRatings" | "collegeRatings", code: string, value: string) => void;
}) {
  const delayed = form.programCompletion === ProgramCompletion.WITH_SOME_DELAY;
  const hasDelayOther = form.delayReasons.includes(DelayReason.OTHER);
  const hasLearningOther = form.significantLearningExperiences.includes(SignificantLearning.OTHER);
  const hasWork = form.careerModes.includes(CareerMode.WORK);
  const hasStudy = form.careerModes.includes(CareerMode.STUDY);

  return (
    <>
      <ExitInterviewSection title="General information" id="exit-interview-general-information">
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          These values belong to this Exit Interview only. Changes here do not update your Account Profile or Individual Inventory.
        </p>
        <div className="mt-5 grid gap-x-6 gap-y-5 sm:grid-cols-2">
          <FormField id="exit-student-name" label="Student name" value={form.studentName} disabled={disabled} onChange={(value) => onTextChange("studentName", value)} />
          <FormField id="exit-age" label="Age" type="number" min={0} max={150} value={form.age} disabled={disabled} onChange={(value) => onTextChange("age", value)} />
          <FormField id="exit-civil-status" label="Civil Status" value={form.civilStatus} disabled={disabled} onChange={(value) => onTextChange("civilStatus", value)} />
          <FormField id="exit-course" label="Course" value={form.course} disabled={disabled} onChange={(value) => onTextChange("course", value)} />
          <FormField id="exit-major" label="Major" value={form.major} disabled={disabled} onChange={(value) => onTextChange("major", value)} />
          <FormField id="exit-email-address" label="Email Address" type="email" value={form.emailAddress} disabled={disabled} onChange={(value) => onTextChange("emailAddress", value)} />
          <FormField id="exit-contact-number" label="Contact Number" type="tel" value={form.contactNumber} disabled={disabled} onChange={(value) => onTextChange("contactNumber", value)} />
          <div className="sm:col-span-2">
            <FormTextArea id="exit-home-address" label="Home Address" value={form.homeAddress} disabled={disabled} onChange={(value) => onTextChange("homeAddress", value)} />
          </div>
        </div>
      </ExitInterviewSection>

      <ExitInterviewSection title="Section I — Program completion and plans" id="exit-interview-program-completion">
        <fieldset className="mt-4">
          <legend className="text-sm font-semibold text-ink">Program completion</legend>
          <div className="mt-2 flex flex-col gap-1 sm:flex-row sm:gap-6">
            {PROGRAM_COMPLETION_CHOICES.map(({ value, label }) => (
              <label key={value} className="flex min-h-9 items-center gap-2 text-sm text-ink">
                <input
                  type="radio"
                  name="exit-program-completion"
                  value={value}
                  checked={form.programCompletion === value}
                  disabled={disabled}
                  onChange={() => onProgramCompletionChange(value)}
                  className="h-4 w-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        {delayed ? (
          <div className="mt-4 max-w-2xl space-y-4 border-l-2 border-border pl-4">
            <FormField id="exit-extra-terms" label="Number of extra terms" type="number" min={1} value={form.extraTermsCount} disabled={disabled} onChange={(value) => onTextChange("extraTermsCount", value)} />
            <fieldset>
              <legend className="text-sm font-semibold text-ink">Reason for delay</legend>
              <div className="mt-2 space-y-1">
                {DELAY_REASONS.map((choice) => (
                  <ChoiceCheckbox
                    key={choice.value}
                    id={`exit-delay-${choice.value.toLowerCase()}`}
                    label={choice.label}
                    checked={form.delayReasons.includes(choice.value)}
                    disabled={disabled}
                    onChange={() => onToggleDelayReason(choice.value)}
                  />
                ))}
              </div>
            </fieldset>
            {hasDelayOther ? (
              <FormTextArea id="exit-delay-other" label="Specify other reason" value={form.delayOther} required disabled={disabled} onChange={(value) => onTextChange("delayOther", value)} />
            ) : null}
          </div>
        ) : null}

        <div className="mt-7 border-t border-border pt-5">
          <h3 className="font-semibold text-ink">Significant learning experiences</h3>
          <fieldset className="mt-2">
            <legend className="sr-only">Select significant learning experiences</legend>
            <div className="grid gap-x-6 sm:grid-cols-2">
              {SIGNIFICANT_LEARNING_CHOICES.map((choice) => (
                <ChoiceCheckbox
                  key={choice.value}
                  id={`exit-learning-${choice.value.toLowerCase()}`}
                  label={choice.label}
                  checked={form.significantLearningExperiences.includes(choice.value)}
                  disabled={disabled}
                  onChange={() => onToggleLearning(choice.value)}
                />
              ))}
            </div>
          </fieldset>
          {hasLearningOther ? (
            <div className="mt-3 max-w-2xl">
              <FormTextArea id="exit-learning-other" label="Specify other experience" value={form.significantLearningOther} required disabled={disabled} onChange={(value) => onTextChange("significantLearningOther", value)} />
            </div>
          ) : null}
        </div>

        <div className="mt-7 border-t border-border pt-5">
          <h3 className="font-semibold text-ink">Career plans</h3>
          <p className="mt-1 text-sm text-muted">Work and Study are independent choices. You may select both.</p>
          <div className="mt-3 grid gap-6 lg:grid-cols-2">
            <fieldset>
              <legend className="font-semibold text-ink">Work</legend>
              <ChoiceCheckbox id="exit-career-work" label="Work" checked={hasWork} disabled={disabled} onChange={() => onToggleCareerMode(CareerMode.WORK)} />
              {hasWork ? (
                <div className="mt-2 border-l-2 border-border pl-4">
                  {WORK_CHOICES.map((choice) => (
                    <ChoiceCheckbox
                      key={choice.value}
                      id={`exit-work-${choice.value.toLowerCase()}`}
                      label={choice.label}
                      checked={form.workChoices.includes(choice.value)}
                      disabled={disabled}
                      onChange={() => onToggleWorkChoice(choice.value)}
                    />
                  ))}
                </div>
              ) : null}
            </fieldset>
            <fieldset>
              <legend className="font-semibold text-ink">Study</legend>
              <ChoiceCheckbox id="exit-career-study" label="Study" checked={hasStudy} disabled={disabled} onChange={() => onToggleCareerMode(CareerMode.STUDY)} />
              {hasStudy ? (
                <div className="mt-2 border-l-2 border-border pl-4">
                  {STUDY_CHOICES.map((choice) => (
                    <ChoiceCheckbox
                      key={choice.value}
                      id={`exit-study-${choice.value.toLowerCase()}`}
                      label={choice.label}
                      checked={form.studyChoices.includes(choice.value)}
                      disabled={disabled}
                      onChange={() => onToggleStudyChoice(choice.value)}
                    />
                  ))}
                </div>
              ) : null}
            </fieldset>
          </div>
        </div>
      </ExitInterviewSection>

      <ExitInterviewSection title="Section II — Self-Assessment" id="exit-interview-self-assessment">
        <p className="mt-2 text-sm leading-6 text-muted">
          Rate each item using the source scale: 5 — Much enhanced; 4 — Enhanced; 3 — No Difference; 2 — Became Worse; 1 — I don&apos;t know.
        </p>
        <RatingMatrix
          title="Self-Assessment"
          items={SELF_ASSESSMENT_ITEMS}
          values={form.selfRatings}
          scale={SELF_ASSESSMENT_SCALE}
          disabled={disabled}
          onChange={(code, value) => onRatingChange("selfRatings", code, value)}
        />
      </ExitInterviewSection>

      <ExitInterviewSection title="Section III — College Feedback" id="exit-interview-college-feedback">
        <p className="mt-2 text-sm leading-6 text-muted">
          5 — Highly Satisfactory; 4 — Satisfactory; 3 — Average; 2 — Unsatisfactory; 1 — Very Unsatisfactory.
        </p>
        <p className="mt-2 text-sm text-muted">
          The source form includes 0 as a response option but does not specify its meaning.
        </p>
        {COLLEGE_FEEDBACK_CATEGORIES.map((category) => (
          <section key={category.code} aria-labelledby={`exit-feedback-${category.code.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} className="mt-6 border-t border-border pt-5">
            <h3 id={`exit-feedback-${category.code.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} className="font-semibold text-ink">{category.label}</h3>
            <RatingMatrix
              title={`College Feedback ${category.label}`}
              items={category.items}
              values={form.collegeRatings}
              scale={COLLEGE_FEEDBACK_SCALE}
              zeroChoice
              disabled={disabled}
              onChange={(code, value) => onRatingChange("collegeRatings", code, value)}
            />
            <div className="mt-4 max-w-3xl">
              <FormTextArea
                id={`exit-comment-${category.commentKey}`}
                label={category.commentLabel}
                value={form[category.commentKey]}
                disabled={disabled}
                onChange={(value) => onTextChange(category.commentKey, value)}
              />
            </div>
          </section>
        ))}
      </ExitInterviewSection>

      <ExitInterviewSection title="Suggestions / Recommendations" id="exit-interview-suggestions">
        <div className="mt-4 max-w-3xl">
          <FormTextArea
            id="exit-suggestions-recommendations"
            label="Suggestions / Recommendations"
            value={form.suggestionsRecommendations}
            disabled={disabled}
            onChange={(value) => onTextChange("suggestionsRecommendations", value)}
          />
        </div>
      </ExitInterviewSection>
    </>
  );
}
