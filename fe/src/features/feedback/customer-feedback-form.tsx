"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { FeedbackAccessUnavailable, FeedbackDate, FeedbackFieldLabel, FeedbackPageHeading, FeedbackRadioGroup, FeedbackSection, feedbackErrorCode, feedbackErrorMessage } from "@/features/feedback/feedback-shared";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { feedbackSubmitCustomerFeedback } from "@/lib/api/generated/feedback/feedback";
import { CustomerFeedbackAccommodatedByValue, CustomerFeedbackRatingValue, CustomerFeedbackServiceValue, type CustomerFeedbackSubmitRequest } from "@/lib/api/generated/model";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";

const serviceChoices: { value: CustomerFeedbackServiceValue; label: string }[] = [
  { value: CustomerFeedbackServiceValue.COUNSELING, label: "Counseling" },
  { value: CustomerFeedbackServiceValue.ADMISSION, label: "Admission" },
  { value: CustomerFeedbackServiceValue.TESTING, label: "Testing" },
  { value: CustomerFeedbackServiceValue.EDUCATIONAL_INFORMATION, label: "Educational Information" },
  { value: CustomerFeedbackServiceValue.REQUEST_FOR_CERTIFICATION, label: "Request for Certification" },
  { value: CustomerFeedbackServiceValue.APPLICATION_FOR_ADMISSION_TEST, label: "Application for Admission Test" },
  { value: CustomerFeedbackServiceValue.OTHER, label: "Others (please specify)" },
];

const customerRatingChoices = [
  { value: CustomerFeedbackRatingValue.NUMBER_5, label: "Excellent" },
  { value: CustomerFeedbackRatingValue.NUMBER_4, label: "Very Good" },
  { value: CustomerFeedbackRatingValue.NUMBER_3, label: "Good" },
  { value: CustomerFeedbackRatingValue.NUMBER_2, label: "Fair" },
  { value: CustomerFeedbackRatingValue.NUMBER_1, label: "Poor" },
] as const;

const ratingRows = [
  ["personnel_accommodating_rating", "Accommodating, attentive & helpfulness"],
  ["personnel_job_knowledge_rating", "Knows the job well"],
  ["personnel_flexibility_rating", "Was flexible in handling request"],
  ["personnel_information_accuracy_rating", "Gave me accurate information"],
  ["personnel_appearance_rating", "Appearance of service personnel"],
  ["personnel_commitment_delivery_rating", "Delivered what was committed"],
  ["office_location_rating", "Conveniently located and easy to find"],
  ["office_cleanliness_rating", "Cleanliness of the premises"],
  ["office_environment_rating", "Conducive working environment"],
  ["office_hours_rating", "Convenient office hours"],
  ["personnel_availability_rating", "Availability of the services of the personnel"],
  ["overall_satisfaction_rating", "Overall, how satisfied are you with your customer experience?"],
] as const;

type RatingKey = (typeof ratingRows)[number][0];
type Draft = {
  services: CustomerFeedbackServiceValue[];
  otherService: string;
  talkedToCounselor: "" | "yes" | "no";
  accommodatedBy: CustomerFeedbackAccommodatedByValue | "";
  officeVisitCount: string;
  ratings: Partial<Record<RatingKey, CustomerFeedbackRatingValue>>;
  transactionDuration: string;
  additionalFeedback: string;
  futureServiceImprovement: string;
  courseYear: string;
};

type RespondentOverrides = { name?: string; address?: string; mobile?: string };
type SubmissionIntent = { fingerprint: string; key: string; body: CustomerFeedbackSubmitRequest };

const emptyDraft: Draft = {
  services: [], otherService: "", talkedToCounselor: "", accommodatedBy: "",
  officeVisitCount: "", ratings: {}, transactionDuration: "", additionalFeedback: "",
  futureServiceImprovement: "", courseYear: "",
};

function makeBody(draft: Draft, respondent: { name: string; address: string; mobile: string }): CustomerFeedbackSubmitRequest {
  const body: CustomerFeedbackSubmitRequest = {
    services_received: draft.services,
    talked_to_guidance_counselor: draft.talkedToCounselor === "yes",
    office_visit_count: Number(draft.officeVisitCount),
    transaction_duration: draft.transactionDuration.trim(),
    course_year: draft.courseYear.trim(),
    ...(draft.services.includes(CustomerFeedbackServiceValue.OTHER) ? { other_service: draft.otherService.trim() } : {}),
    ...(draft.talkedToCounselor === "no" ? { accommodated_by: draft.accommodatedBy as CustomerFeedbackAccommodatedByValue } : {}),
    ...((respondent.name.trim()) ? { respondent_name: respondent.name.trim() } : {}),
    ...(respondent.address.trim() ? { address: respondent.address.trim() } : {}),
    ...(respondent.mobile.trim() ? { mobile_number: respondent.mobile.trim() } : {}),
    ...(draft.additionalFeedback.trim() ? { additional_feedback: draft.additionalFeedback.trim() } : {}),
    ...(draft.futureServiceImprovement.trim() ? { future_service_improvement: draft.futureServiceImprovement.trim() } : {}),
    ...Object.fromEntries(ratingRows.map(([key]) => [key, draft.ratings[key]])),
  } as CustomerFeedbackSubmitRequest;
  return body;
}

export function CustomerFeedbackForm() {
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);
  const profile = useProfileGetMyProfile({ query: { retry: false, enabled: access.canSubmitCustomerFeedback } });
  const create = useMutation({ mutationFn: ({ body, key }: { body: CustomerFeedbackSubmitRequest; key: string }) => feedbackSubmitCustomerFeedback(body, { headers: { "Idempotency-Key": key } }), retry: false });
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [respondentOverrides, setRespondentOverrides] = useState<RespondentOverrides>({});
  const [confirmationOpen, setConfirmationOpen] = useState(false);
  const [preparedBody, setPreparedBody] = useState<CustomerFeedbackSubmitRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uncertainIntent, setUncertainIntent] = useState<SubmissionIntent | null>(null);
  const [success, setSuccess] = useState<{ submittedAt: string } | null>(null);
  const [serviceError, setServiceError] = useState<string | null>(null);
  const intentRef = useRef<SubmissionIntent | null>(null);
  const isUncertain = uncertainIntent !== null;

  if (!access.canSubmitCustomerFeedback) {
    return <FeedbackAccessUnavailable title="Customer Feedback unavailable" />;
  }

  const profileData = profile.data?.data;
  const respondent = {
    name: respondentOverrides.name ?? profileData?.full_name ?? "",
    address: respondentOverrides.address ?? (profileData?.current_address.trim() ? profileData.current_address : profileData?.permanent_address ?? ""),
    mobile: respondentOverrides.mobile ?? profileData?.contact_number ?? "",
  };

  function changeService(value: CustomerFeedbackServiceValue, checked: boolean) {
    setDraft((current) => {
      const services = checked ? [...current.services, value] : current.services.filter((item) => item !== value);
      return { ...current, services, otherService: services.includes(CustomerFeedbackServiceValue.OTHER) ? current.otherService : "" };
    });
    setServiceError(null);
    setError(null);
  }

  function changeCounselor(value: "yes" | "no") {
    setDraft((current) => ({ ...current, talkedToCounselor: value, accommodatedBy: value === "no" ? current.accommodatedBy : "" }));
    setError(null);
  }

  function prepareSubmission(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setServiceError(null);
    if (isUncertain) return;
    if (!draft.services.length) {
      setServiceError("Select at least one service received.");
      document.getElementById("feedback-services")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    const body = makeBody(draft, respondent);
    setPreparedBody(body);
    setConfirmationOpen(true);
  }

  async function send(body: CustomerFeedbackSubmitRequest) {
    setError(null);
    if (!globalThis.crypto?.randomUUID) {
      setError("This browser cannot create a secure submission request. Update the browser and try again.");
      return;
    }
    const fingerprint = JSON.stringify(body);
    const key = intentRef.current?.fingerprint === fingerprint ? intentRef.current.key : globalThis.crypto.randomUUID();
    const intent = { fingerprint, key, body };
    intentRef.current = intent;
    try {
      const result = await create.mutateAsync({ body, key });
      intentRef.current = null;
      setUncertainIntent(null);
      setSuccess({ submittedAt: result.data.submitted_at });
    } catch (caught) {
      const code = feedbackErrorCode(caught);
      if (code === "idempotency_unavailable" || code === "idempotency_in_progress" || !(caught instanceof Error && "status" in caught)) {
        setUncertainIntent(intent);
        setError(feedbackErrorMessage(caught, "The submission result could not be confirmed. Retry this exact response safely."));
      } else if (code === "idempotency_key_conflict" || code === "invalid_idempotency_key") {
        intentRef.current = null;
        setUncertainIntent(null);
        setError(feedbackErrorMessage(caught, "Review the response and submit again."));
      } else {
        intentRef.current = null;
        setUncertainIntent(null);
        setError(feedbackErrorMessage(caught, "Customer Feedback could not be submitted."));
      }
    }
  }

  if (success) {
    return (
      <section aria-labelledby="customer-feedback-success" className="max-w-2xl">
        <div role="status" className="border-y border-success/30 py-8">
          <h1 id="customer-feedback-success" className="font-heading text-3xl font-bold text-ink">Customer Feedback submitted</h1>
          <p className="mt-3 text-sm leading-6 text-muted">Your response was received{success.submittedAt ? <> on <FeedbackDate value={success.submittedAt} /></> : null}.</p>
          <Link href="/portal/feedback" className="mt-6 inline-flex min-h-10 items-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Feedback</Link>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="customer-feedback-heading">
      <FeedbackPageHeading headingId="customer-feedback-heading" title="Customer Feedback Form" description="Please tell us about the service you received from the GTAO. Your response is submitted as a final response." />
      <form className="mt-4" onSubmit={prepareSubmission} noValidate>
        {error ? <p role="alert" className="mb-5 border-y border-danger/30 py-3 text-sm text-danger">{error}</p> : null}
        {isUncertain ? (
          <div className="mb-6 border-y border-warning/40 bg-warning/10 px-4 py-4" role="status" aria-live="polite">
            <p className="text-sm font-semibold text-ink">Submission result not confirmed</p>
            <p className="mt-1 text-sm leading-6 text-muted">The exact response and its replay key are being retained in this page. Retry the same submission to safely check whether it was received.</p>
            <Button className="mt-3" disabled={create.isPending} onClick={() => void send(uncertainIntent.body)}>{create.isPending ? "Checking submission…" : "Retry same submission"}</Button>
          </div>
        ) : null}
        <fieldset disabled={isUncertain || create.isPending} className="min-w-0 disabled:opacity-75">
          <legend className="sr-only">Customer Feedback response fields</legend>
          <FeedbackSection title="I. Service/s received">
            <fieldset id="feedback-services" className="min-w-0">
              <legend className="text-sm font-semibold text-ink">Check the service/s which you received from the GTAO: <span aria-hidden="true" className="text-danger">*</span></legend>
              {serviceError ? <p id="feedback-services-error" role="alert" className="mt-2 text-sm text-danger">{serviceError}</p> : null}
              <div className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
                {serviceChoices.map((choice) => {
                  const id = `feedback-service-${choice.value.toLowerCase()}`;
                  return <label key={choice.value} htmlFor={id} className="flex min-h-10 items-center gap-3 text-sm text-ink"><input id={id} type="checkbox" className="h-4 w-4 accent-brand" checked={draft.services.includes(choice.value)} onChange={(event) => changeService(choice.value, event.target.checked)} aria-describedby={serviceError ? "feedback-services-error" : undefined} />{choice.label}</label>;
                })}
              </div>
              {draft.services.includes(CustomerFeedbackServiceValue.OTHER) ? (
                <div className="mt-4 max-w-xl">
                  <FeedbackFieldLabel htmlFor="feedback-other-service" required>Please specify</FeedbackFieldLabel>
                  <Input id="feedback-other-service" className="mt-2" required value={draft.otherService} onChange={(event) => setDraft((current) => ({ ...current, otherService: event.target.value }))} />
                </div>
              ) : null}
            </fieldset>
          </FeedbackSection>

          <FeedbackSection title="II. Guidance Counselor and accommodation">
            <FeedbackRadioGroup legend="Were you able to talk to the Guidance Counselor?" name="talked-to-guidance-counselor" value={draft.talkedToCounselor} choices={[{ value: "yes", label: "Yes" }, { value: "no", label: "No" }]} onChange={(value) => changeCounselor(value as "yes" | "no")} required />
            {draft.talkedToCounselor === "no" ? <FeedbackRadioGroup legend="If No, who accommodated you?" name="feedback-accommodated-by" value={draft.accommodatedBy} choices={[{ value: CustomerFeedbackAccommodatedByValue.STUDENT_ASSISTANT, label: "Student Assistant" }, { value: CustomerFeedbackAccommodatedByValue.CLERK_PERSONNEL, label: "Clerk / Personnel" }]} onChange={(value) => setDraft((current) => ({ ...current, accommodatedBy: value as CustomerFeedbackAccommodatedByValue }))} required /> : null}
          </FeedbackSection>

          <FeedbackSection title="III. Number of office visits">
            <div className="max-w-sm">
              <FeedbackFieldLabel htmlFor="feedback-office-visits" required>How many times have you been in the Office?</FeedbackFieldLabel>
              <Input id="feedback-office-visits" className="mt-2" type="number" min={1} max={10000} step={1} required value={draft.officeVisitCount} onChange={(event) => setDraft((current) => ({ ...current, officeVisitCount: event.target.value }))} />
            </div>
          </FeedbackSection>

          <FeedbackSection title="IV. Service personnel experience" description="How well were you served during the visit? Choose one response for each item.">
            <div className="space-y-7">
              {ratingRows.slice(0, 6).map(([key, label], index) => <FeedbackRadioGroup key={key} legend={`${index + 1}. ${label}`} name={`feedback-rating-${key}`} value={draft.ratings[key] ?? null} choices={customerRatingChoices} onChange={(value) => setDraft((current) => ({ ...current, ratings: { ...current.ratings, [key]: value as CustomerFeedbackRatingValue } }))} columns={3} required />)}
            </div>
            <div className="max-w-xl pt-2">
              <FeedbackFieldLabel htmlFor="feedback-transaction-duration" required>How long did it take you to finish the transactions?</FeedbackFieldLabel>
              <Input id="feedback-transaction-duration" className="mt-2" required value={draft.transactionDuration} onChange={(event) => setDraft((current) => ({ ...current, transactionDuration: event.target.value }))} />
            </div>
          </FeedbackSection>

          <FeedbackSection title="V. Office experience" description="How did you find our college/office? Choose one response for each item.">
            <div className="space-y-7">
              {ratingRows.slice(6, 11).map(([key, label], index) => <FeedbackRadioGroup key={key} legend={`${index + 1}. ${label}`} name={`feedback-rating-${key}`} value={draft.ratings[key] ?? null} choices={customerRatingChoices} onChange={(value) => setDraft((current) => ({ ...current, ratings: { ...current.ratings, [key]: value as CustomerFeedbackRatingValue } }))} columns={3} required />)}
            </div>
          </FeedbackSection>

          <FeedbackSection title="VI. Overall satisfaction">
            <FeedbackRadioGroup legend={ratingRows[11][1]} name="feedback-rating-overall_satisfaction_rating" value={draft.ratings.overall_satisfaction_rating ?? null} choices={customerRatingChoices} onChange={(value) => setDraft((current) => ({ ...current, ratings: { ...current.ratings, overall_satisfaction_rating: value as CustomerFeedbackRatingValue } }))} columns={3} required />
          </FeedbackSection>

          <FeedbackSection title="VII. Additional feedback">
            <div className="max-w-3xl">
              <FeedbackFieldLabel htmlFor="feedback-additional">Any more feedback for us regarding your experience?</FeedbackFieldLabel>
              <Textarea id="feedback-additional" className="mt-2 min-h-28" value={draft.additionalFeedback} onChange={(event) => setDraft((current) => ({ ...current, additionalFeedback: event.target.value }))} />
            </div>
          </FeedbackSection>

          <FeedbackSection title="VIII. Future service improvement">
            <div className="max-w-3xl">
              <FeedbackFieldLabel htmlFor="feedback-future-improvement">Please tell us how we might better serve you in the future?</FeedbackFieldLabel>
              <Textarea id="feedback-future-improvement" className="mt-2 min-h-28" value={draft.futureServiceImprovement} onChange={(event) => setDraft((current) => ({ ...current, futureServiceImprovement: event.target.value }))} />
            </div>
          </FeedbackSection>

          <FeedbackSection title="IX. Respondent information" description="These details are part of this response and remain editable.">
            <p className="max-w-3xl text-sm leading-6 text-muted">Changes made here apply only to this feedback response and do not update your account profile.</p>
            {profile.isError ? <p role="status" className="text-sm text-muted">Your profile details could not be loaded. You can enter them manually.</p> : null}
            <div className="grid gap-5 sm:grid-cols-2">
              <div><FeedbackFieldLabel htmlFor="feedback-respondent-name">Name</FeedbackFieldLabel><Input id="feedback-respondent-name" className="mt-2" value={respondent.name} onChange={(event) => setRespondentOverrides((current) => ({ ...current, name: event.target.value }))} /></div>
              <div><FeedbackFieldLabel htmlFor="feedback-course-year" required>Course/Year</FeedbackFieldLabel><Input id="feedback-course-year" className="mt-2" required value={draft.courseYear} onChange={(event) => setDraft((current) => ({ ...current, courseYear: event.target.value }))} /></div>
              <div><FeedbackFieldLabel htmlFor="feedback-address">Address</FeedbackFieldLabel><Input id="feedback-address" className="mt-2" value={respondent.address} onChange={(event) => setRespondentOverrides((current) => ({ ...current, address: event.target.value }))} /></div>
              <div><FeedbackFieldLabel htmlFor="feedback-mobile">Mobile Number</FeedbackFieldLabel><Input id="feedback-mobile" className="mt-2" inputMode="tel" value={respondent.mobile} onChange={(event) => setRespondentOverrides((current) => ({ ...current, mobile: event.target.value }))} /></div>
            </div>
          </FeedbackSection>
        </fieldset>

        {create.isPending ? <p role="status" aria-live="polite" className="mb-4 text-sm text-muted">Submitting Customer Feedback…</p> : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-border pt-5">
          <Button type="submit" disabled={create.isPending || isUncertain}>{create.isPending ? "Submitting…" : "Review and submit"}</Button>
          <Link href="/portal/feedback" className="inline-flex min-h-10 items-center rounded-md px-3 text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Feedback</Link>
        </div>
      </form>

      <AlertDialog open={confirmationOpen} onOpenChange={setConfirmationOpen}>
        <AlertDialogContent>
          <AlertDialogTitle>Submit Customer Feedback?</AlertDialogTitle>
          <AlertDialogDescription>Your response will be submitted as a final response. COMPASS does not provide editing or response history after submission.</AlertDialogDescription>
          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <AlertDialogCancel asChild><Button variant="secondary" onClick={() => setPreparedBody(null)}>Review response</Button></AlertDialogCancel>
            <AlertDialogAction asChild><Button disabled={create.isPending} onClick={(event) => { event.preventDefault(); setConfirmationOpen(false); if (preparedBody) void send(preparedBody); }}>{create.isPending ? "Submitting…" : "Submit Customer Feedback"}</Button></AlertDialogAction>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
