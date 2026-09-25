"use client";

import Link from "next/link";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { FeedbackAccessUnavailable, FeedbackPageHeading, FeedbackQueryError, FeedbackRatingLabel, feedbackErrorCode } from "@/features/feedback/feedback-shared";
import { useFeedbackGetCustomerFeedbackResponse, useFeedbackGetCsmResponse } from "@/lib/api/generated/feedback/feedback";
import { CSMCC1Value, CSMCC2Value, CSMCC3Value, CSMClientTypeValue, CSMRatingValue, CSMSexValue, CustomerFeedbackAccommodatedByValue, CustomerFeedbackServiceValue } from "@/lib/api/generated/model";

const serviceLabels: Record<CustomerFeedbackServiceValue, string> = {
  [CustomerFeedbackServiceValue.COUNSELING]: "Counseling",
  [CustomerFeedbackServiceValue.ADMISSION]: "Admission",
  [CustomerFeedbackServiceValue.TESTING]: "Testing",
  [CustomerFeedbackServiceValue.EDUCATIONAL_INFORMATION]: "Educational Information",
  [CustomerFeedbackServiceValue.REQUEST_FOR_CERTIFICATION]: "Request for Certification",
  [CustomerFeedbackServiceValue.APPLICATION_FOR_ADMISSION_TEST]: "Application for Admission Test",
  [CustomerFeedbackServiceValue.OTHER]: "Others",
};

const customerRatings = [
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

const sqdQuestions = [
  "I am satisfied with the service that I availed.",
  "I spent a reasonable amount of time for my transaction.",
  "The office followed the transaction's requirements and steps based on the information provided.",
  "The steps (including payment) I needed to do for my transaction were easy and simple.",
  "I easily found information about my transaction from the office or its website.",
  "I paid a reasonable amount of fees for my transaction.",
  'I feel the office was fair to everyone, or "walang palakasan", during my transaction.',
  "I was treated courteously by the staff, and (if asked for help) the staff was helpful.",
  "I got what I needed from the government office, or (if denied) denial of request was sufficiently explained to me.",
] as const;

function DetailField({ label, children }: { label: string; children: React.ReactNode }) {
  const empty = children === null || children === undefined || children === "";
  return <div className="min-w-0"><dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{empty ? "Not provided" : children}</dd></div>;
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="border-t border-border py-6"><h2 className="font-heading text-lg font-semibold text-ink">{title}</h2><dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">{children}</dl></section>;
}

function notFoundMessage(error: unknown, instrument: "Customer Feedback" | "CSM"): string | null {
  if (feedbackErrorCode(error) === "feedback_not_found" || (error && typeof error === "object" && "status" in error && error.status === 404)) {
    return instrument === "CSM" ? "CSM response not found" : "Feedback response not found";
  }
  return null;
}

export function CustomerFeedbackResponseDetail({ responseId }: { responseId: string }) {
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);
  const detail = useFeedbackGetCustomerFeedbackResponse(responseId, { query: { retry: false, enabled: access.canViewCustomerFeedback } });
  if (!access.canViewCustomerFeedback) return <FeedbackAccessUnavailable title="Customer Feedback response unavailable" />;
  if (detail.isPending) return <p aria-busy="true" className="py-8 text-sm text-muted">Loading Customer Feedback response…</p>;
  if (detail.isError) {
    const missing = notFoundMessage(detail.error, "Customer Feedback");
    return <section><FeedbackPageHeading title={missing ?? "Customer Feedback response could not be loaded"} /><div className="mt-5">{missing ? <Link href="/portal/feedback/customer-feedback/responses" className="text-sm font-semibold text-brand underline">Back to responses</Link> : <FeedbackQueryError error={detail.error} fallback="Customer Feedback response could not be loaded." onRetry={() => void detail.refetch()} />}</div></section>;
  }
  const item = detail.data.data;
  const services = item.services_received.map((value) => serviceLabels[value] ?? value).join(", ");

  return (
    <section aria-labelledby="customer-feedback-detail-heading">
      <FeedbackPageHeading headingId="customer-feedback-detail-heading" eyebrow="Customer Feedback response" title={item.respondent_name || "Customer Feedback response"} description={`Submitted ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.submitted_at))}.`} action={<Link href="/portal/feedback/customer-feedback/responses" className="inline-flex min-h-10 items-center rounded-md border border-border-strong px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to responses</Link>} />
      <DetailSection title="I. Service/s received">
        <DetailField label="Services received">{services}</DetailField>
        {item.services_received.includes(CustomerFeedbackServiceValue.OTHER) ? <DetailField label="Other service specified">{item.other_service}</DetailField> : null}
      </DetailSection>
      <DetailSection title="II. Guidance Counselor and accommodation">
        <DetailField label="Talked to Guidance Counselor">{item.talked_to_guidance_counselor ? "Yes" : "No"}</DetailField>
        {!item.talked_to_guidance_counselor && item.accommodated_by ? <DetailField label="Accommodated by">{item.accommodated_by === CustomerFeedbackAccommodatedByValue.STUDENT_ASSISTANT ? "Student Assistant" : "Clerk / Personnel"}</DetailField> : null}
      </DetailSection>
      <DetailSection title="III. Number of office visits"><DetailField label="How many times have you been in the Office?">{item.office_visit_count}</DetailField></DetailSection>
      <DetailSection title="IV. Service personnel experience">
        {customerRatings.slice(0, 6).map(([key, label]) => <DetailField key={key} label={label}><FeedbackRatingLabel value={item[key]} /></DetailField>)}
        <DetailField label="Transaction duration">{item.transaction_duration}</DetailField>
      </DetailSection>
      <DetailSection title="V. Office experience">{customerRatings.slice(6, 11).map(([key, label]) => <DetailField key={key} label={label}><FeedbackRatingLabel value={item[key]} /></DetailField>)}</DetailSection>
      <DetailSection title="VI. Overall satisfaction"><DetailField label="Overall, how satisfied are you with your customer experience?"><FeedbackRatingLabel value={item.overall_satisfaction_rating} /></DetailField></DetailSection>
      <DetailSection title="VII. Additional feedback"><DetailField label="Any more feedback for us regarding your experience?">{item.additional_feedback}</DetailField></DetailSection>
      <DetailSection title="VIII. Future service improvement"><DetailField label="Please tell us how we might better serve you in the future?">{item.future_service_improvement}</DetailField></DetailSection>
      <DetailSection title="IX. Respondent information">
        <DetailField label="Name">{item.respondent_name}</DetailField><DetailField label="Course/Year">{item.course_year}</DetailField>
        <DetailField label="Address">{item.address}</DetailField><DetailField label="Mobile Number">{item.mobile_number}</DetailField>
      </DetailSection>
      <DetailSection title="Form Revision provenance">
        <DetailField label="Official code">{item.form_revision.official_code}</DetailField><DetailField label="Official revision">{item.form_revision.official_revision}</DetailField>
        <DetailField label="Internal schema version">{item.form_revision.internal_schema_version}</DetailField>
      </DetailSection>
    </section>
  );
}

function cc1Label(value: CSMCC1Value): string {
  return ({
    [CSMCC1Value.NUMBER_1]: "I know what a CC is and I saw this office's CC.",
    [CSMCC1Value.NUMBER_2]: "I know what a CC is but I did NOT see this office's CC.",
    [CSMCC1Value.NUMBER_3]: "I learned of the CC only when I saw this office's CC.",
    [CSMCC1Value.NUMBER_4]: "I do not know what a CC is and I did not see one in this office.",
  })[value];
}

function cc2Label(value: CSMCC2Value): string {
  return ({ [CSMCC2Value.NUMBER_1]: "Easy to see", [CSMCC2Value.NUMBER_2]: "Somewhat easy to see", [CSMCC2Value.NUMBER_3]: "Difficult to see", [CSMCC2Value.NUMBER_4]: "Not visible at all", [CSMCC2Value.NUMBER_5]: "N/A" })[value];
}

function cc3Label(value: CSMCC3Value): string {
  return ({ [CSMCC3Value.NUMBER_1]: "Helped very much", [CSMCC3Value.NUMBER_2]: "Somewhat helped", [CSMCC3Value.NUMBER_3]: "Did not help", [CSMCC3Value.NUMBER_4]: "N/A" })[value];
}

function csmRatingLabel(value: CSMRatingValue): string {
  return ({ [CSMRatingValue.NUMBER_0]: "Not Applicable", [CSMRatingValue.NUMBER_1]: "Strongly Disagree", [CSMRatingValue.NUMBER_2]: "Disagree", [CSMRatingValue.NUMBER_3]: "Neither Agree nor Disagree", [CSMRatingValue.NUMBER_4]: "Agree", [CSMRatingValue.NUMBER_5]: "Strongly Agree" })[value];
}

export function CsmResponseDetail({ responseId }: { responseId: string }) {
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);
  const detail = useFeedbackGetCsmResponse(responseId, { query: { retry: false, enabled: access.canViewCsm } });
  if (!access.canViewCsm) return <FeedbackAccessUnavailable title="CSM response unavailable" />;
  if (detail.isPending) return <p aria-busy="true" className="py-8 text-sm text-muted">Loading CSM response…</p>;
  if (detail.isError) {
    const missing = notFoundMessage(detail.error, "CSM");
    return <section><FeedbackPageHeading title={missing ?? "CSM response could not be loaded"} /><div className="mt-5">{missing ? <Link href="/portal/feedback/csm/responses" className="text-sm font-semibold text-brand underline">Back to responses</Link> : <FeedbackQueryError error={detail.error} fallback="CSM response could not be loaded." onRetry={() => void detail.refetch()} />}</div></section>;
  }
  const item = detail.data.data;
  const clientLabel = item.client_type === CSMClientTypeValue.CITIZEN ? "Citizen" : item.client_type === CSMClientTypeValue.BUSINESS ? "Business" : "Government";

  return (
    <section aria-labelledby="csm-detail-heading">
      <FeedbackPageHeading headingId="csm-detail-heading" title="Client Satisfaction Measurement response" description={`Submitted ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.submitted_at))}.`} action={<Link href="/portal/feedback/csm/responses" className="inline-flex min-h-10 items-center rounded-md border border-border-strong px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to responses</Link>} />
      <DetailSection title="Respondent and instrument data">
        <DetailField label="Client type">{clientLabel}</DetailField>
        <DetailField label="Sex">{item.sex === CSMSexValue.MALE ? "Male" : "Female"}</DetailField>
        <DetailField label="Age">{item.age}</DetailField>
        <DetailField label="Region of Residence">{item.region_of_residence}</DetailField>
        <DetailField label="Service Availed">{item.service_availed}</DetailField>
      </DetailSection>
      <DetailSection title="Citizen's Charter">
        <DetailField label="CC1. Which of the following best describes your awareness of a CC?">{cc1Label(item.cc1)}</DetailField>
        <DetailField label="CC2. Visibility of this office's CC">{cc2Label(item.cc2)}</DetailField>
        <DetailField label="CC3. Helpfulness of the CC in your transaction">{cc3Label(item.cc3)}</DetailField>
      </DetailSection>
      <DetailSection title="Service Quality">
        {sqdQuestions.map((question, index) => <DetailField key={`sqd${index}`} label={`SQD${index}. ${question}`}>{csmRatingLabel(item[`sqd${index}` as keyof typeof item] as CSMRatingValue)}</DetailField>)}
      </DetailSection>
      <DetailSection title="Additional information">
        <DetailField label="Suggestions on how we can further improve our services">{item.suggestions}</DetailField>
        <DetailField label="Email address">{item.email || "Not provided"}</DetailField>
        <DetailField label="Instrument schema version">{item.instrument_schema_version}</DetailField>
      </DetailSection>
    </section>
  );
}
