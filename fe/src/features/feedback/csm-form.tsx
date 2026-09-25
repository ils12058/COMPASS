"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { FeedbackAccessUnavailable, FeedbackDate, FeedbackFieldLabel, FeedbackPageHeading, FeedbackRadioGroup, FeedbackSection, feedbackErrorCode, feedbackErrorMessage } from "@/features/feedback/feedback-shared";
import { feedbackSubmitCsm } from "@/lib/api/generated/feedback/feedback";
import { CSMCC1Value, CSMCC2Value, CSMCC3Value, CSMClientTypeValue, CSMRatingValue, CSMSexValue, type CSMSubmitRequest } from "@/lib/api/generated/model";

const clientTypeChoices = [
  { value: CSMClientTypeValue.CITIZEN, label: "Citizen" },
  { value: CSMClientTypeValue.BUSINESS, label: "Business" },
  { value: CSMClientTypeValue.GOVERNMENT, label: "Government (Employee or another agency)" },
] as const;

const sexChoices = [
  { value: CSMSexValue.MALE, label: "Male" },
  { value: CSMSexValue.FEMALE, label: "Female" },
] as const;

const cc1Choices = [
  { value: CSMCC1Value.NUMBER_1, label: "I know what a CC is and I saw this office's CC." },
  { value: CSMCC1Value.NUMBER_2, label: "I know what a CC is but I did NOT see this office's CC." },
  { value: CSMCC1Value.NUMBER_3, label: "I learned of the CC only when I saw this office's CC." },
  { value: CSMCC1Value.NUMBER_4, label: "I do not know what a CC is and I did not see one in this office." },
] as const;

const cc2Choices = [
  { value: CSMCC2Value.NUMBER_1, label: "Easy to see" },
  { value: CSMCC2Value.NUMBER_2, label: "Somewhat easy to see" },
  { value: CSMCC2Value.NUMBER_3, label: "Difficult to see" },
  { value: CSMCC2Value.NUMBER_4, label: "Not visible at all" },
  { value: CSMCC2Value.NUMBER_5, label: "N/A" },
] as const;

const cc3Choices = [
  { value: CSMCC3Value.NUMBER_1, label: "Helped very much" },
  { value: CSMCC3Value.NUMBER_2, label: "Somewhat helped" },
  { value: CSMCC3Value.NUMBER_3, label: "Did not help" },
  { value: CSMCC3Value.NUMBER_4, label: "N/A" },
] as const;

const sqdChoices = [
  { value: CSMRatingValue.NUMBER_1, label: "Strongly Disagree" },
  { value: CSMRatingValue.NUMBER_2, label: "Disagree" },
  { value: CSMRatingValue.NUMBER_3, label: "Neither Agree nor Disagree" },
  { value: CSMRatingValue.NUMBER_4, label: "Agree" },
  { value: CSMRatingValue.NUMBER_5, label: "Strongly Agree" },
  { value: CSMRatingValue.NUMBER_0, label: "Not Applicable" },
] as const;

const sqdQuestions = [
  ["sqd0", "I am satisfied with the service that I availed."],
  ["sqd1", "I spent a reasonable amount of time for my transaction."],
  ["sqd2", "The office followed the transaction's requirements and steps based on the information provided."],
  ["sqd3", "The steps (including payment) I needed to do for my transaction were easy and simple."],
  ["sqd4", "I easily found information about my transaction from the office or its website."],
  ["sqd5", "I paid a reasonable amount of fees for my transaction."],
  ["sqd6", 'I feel the office was fair to everyone, or "walang palakasan", during my transaction.'],
  ["sqd7", "I was treated courteously by the staff, and (if asked for help) the staff was helpful."],
  ["sqd8", "I got what I needed from the government office, or (if denied) denial of request was sufficiently explained to me."],
] as const;

type SqdKey = (typeof sqdQuestions)[number][0];
type CsmDraft = {
  clientType: CSMClientTypeValue | "";
  sex: CSMSexValue | "";
  age: string;
  region: string;
  service: string;
  cc1: CSMCC1Value | "";
  cc2: CSMCC2Value | "";
  cc3: CSMCC3Value | "";
  sqds: Partial<Record<SqdKey, CSMRatingValue>>;
  suggestions: string;
  email: string;
};

type CsmIntent = { fingerprint: string; key: string; body: CSMSubmitRequest };

const emptyCsmDraft: CsmDraft = {
  clientType: "", sex: "", age: "", region: "", service: "", cc1: "", cc2: "", cc3: "", sqds: {}, suggestions: "", email: "",
};

function makeCsmBody(draft: CsmDraft): CSMSubmitRequest {
  return {
    client_type: draft.clientType as CSMClientTypeValue,
    sex: draft.sex as CSMSexValue,
    age: Number(draft.age),
    region_of_residence: draft.region.trim(),
    service_availed: draft.service.trim(),
    cc1: draft.cc1 as CSMCC1Value,
    cc2: draft.cc2 as CSMCC2Value,
    cc3: draft.cc3 as CSMCC3Value,
    ...Object.fromEntries(sqdQuestions.map(([key]) => [key, draft.sqds[key]])),
    ...(draft.suggestions.trim() ? { suggestions: draft.suggestions.trim() } : {}),
    ...(draft.email.trim() ? { email: draft.email.trim() } : {}),
  } as CSMSubmitRequest;
}

export function CsmForm() {
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);
  const create = useMutation({ mutationFn: ({ body, key }: { body: CSMSubmitRequest; key: string }) => feedbackSubmitCsm(body, { headers: { "Idempotency-Key": key } }), retry: false });
  const [draft, setDraft] = useState<CsmDraft>(emptyCsmDraft);
  const [confirmationOpen, setConfirmationOpen] = useState(false);
  const [preparedBody, setPreparedBody] = useState<CSMSubmitRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uncertainIntent, setUncertainIntent] = useState<CsmIntent | null>(null);
  const [success, setSuccess] = useState<{ submittedAt: string } | null>(null);
  const intentRef = useRef<CsmIntent | null>(null);
  const isUncertain = uncertainIntent !== null;

  if (!access.canSubmitCsm) return <FeedbackAccessUnavailable title="Client Satisfaction Measurement unavailable" />;

  function changeCc1(value: CSMCC1Value) {
    setDraft((current) => ({
      ...current,
      cc1: value,
      cc2: value === CSMCC1Value.NUMBER_4
        ? CSMCC2Value.NUMBER_5
        : current.cc1 === CSMCC1Value.NUMBER_4 ? "" : current.cc2,
      cc3: value === CSMCC1Value.NUMBER_4
        ? CSMCC3Value.NUMBER_4
        : current.cc1 === CSMCC1Value.NUMBER_4 ? "" : current.cc3,
    }));
  }

  function prepareSubmission(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (isUncertain) return;
    if (!event.currentTarget.reportValidity()) return;
    setPreparedBody(makeCsmBody(draft));
    setConfirmationOpen(true);
  }

  async function send(body: CSMSubmitRequest) {
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
        setError(feedbackErrorMessage(caught, "Client Satisfaction Measurement could not be submitted."));
      }
    }
  }

  if (success) {
    return (
      <section aria-labelledby="csm-success-heading" className="max-w-2xl">
        <div role="status" className="border-y border-success/30 py-8">
          <h1 id="csm-success-heading" className="font-heading text-3xl font-bold text-ink">Client Satisfaction Measurement submitted</h1>
          <p className="mt-3 text-sm leading-6 text-muted">Your response was received{success.submittedAt ? <> on <FeedbackDate value={success.submittedAt} /></> : null}.</p>
          <Link href="/portal/feedback" className="mt-6 inline-flex min-h-10 items-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Feedback</Link>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="csm-page-heading">
      <FeedbackPageHeading headingId="csm-page-heading" eyebrow="Client Satisfaction Measurement" title="HELP US SERVE YOU BETTER!" description="The Client Satisfaction Measurement gathers feedback about customer experience with government offices. Taking part is optional; if you choose to continue, please answer the required questions." />
      <form className="mt-4" onSubmit={prepareSubmission} noValidate>
        {error ? <p role="alert" className="mb-5 border-y border-danger/30 py-3 text-sm text-danger">{error}</p> : null}
        {isUncertain ? <div className="mb-6 border-y border-warning/40 bg-warning/10 px-4 py-4" role="status" aria-live="polite"><p className="text-sm font-semibold text-ink">Submission result not confirmed</p><p className="mt-1 text-sm leading-6 text-muted">The exact response and its replay key are being retained in this page. Retry the same submission to safely check whether it was received.</p><Button className="mt-3" disabled={create.isPending} onClick={() => void send(uncertainIntent.body)}>{create.isPending ? "Checking submission…" : "Retry same submission"}</Button></div> : null}
        <fieldset disabled={isUncertain || create.isPending} className="min-w-0 disabled:opacity-75">
          <legend className="sr-only">Client Satisfaction Measurement response fields</legend>
          <FeedbackSection title="Respondent information">
            <p className="max-w-3xl text-sm leading-6 text-muted">Please select the type that best describes you and provide the following information.</p>
            <FeedbackRadioGroup legend="Client type" name="csm-client-type" value={draft.clientType} choices={clientTypeChoices} onChange={(value) => setDraft((current) => ({ ...current, clientType: value as CSMClientTypeValue }))} required />
            <FeedbackRadioGroup legend="Sex" name="csm-sex" value={draft.sex} choices={sexChoices} onChange={(value) => setDraft((current) => ({ ...current, sex: value as CSMSexValue }))} required />
            <div className="grid gap-5 sm:grid-cols-2">
              <div><FeedbackFieldLabel htmlFor="csm-age" required>Age</FeedbackFieldLabel><Input id="csm-age" className="mt-2" type="number" min={0} max={150} step={1} required value={draft.age} onChange={(event) => setDraft((current) => ({ ...current, age: event.target.value }))} /></div>
              <div><FeedbackFieldLabel htmlFor="csm-region" required>Region of Residence</FeedbackFieldLabel><Input id="csm-region" className="mt-2" required value={draft.region} onChange={(event) => setDraft((current) => ({ ...current, region: event.target.value }))} /></div>
              <div className="sm:col-span-2"><FeedbackFieldLabel htmlFor="csm-service" required>Service Availed</FeedbackFieldLabel><Input id="csm-service" className="mt-2" required value={draft.service} onChange={(event) => setDraft((current) => ({ ...current, service: event.target.value }))} /></div>
            </div>
          </FeedbackSection>

          <FeedbackSection title="Citizen's Charter" description="The Citizen's Charter is an official document that reflects the services of a government agency or office, including requirements, fees, and processing times, among others.">
            <FeedbackRadioGroup legend="CC1. Which of the following best describes your awareness of a CC?" name="csm-cc1" value={draft.cc1} choices={cc1Choices} onChange={(value) => changeCc1(value as CSMCC1Value)} required />
            {draft.cc1 === CSMCC1Value.NUMBER_4 ? (
              <div className="space-y-5 rounded-md border border-border bg-surface-muted p-4" aria-live="polite">
                <p className="text-sm text-muted">Because you answered that you do not know what a CC is and did not see one, CC2 and CC3 are recorded as Not Applicable.</p>
                <p className="text-sm"><span className="font-semibold text-ink">CC2. Visibility of this office&apos;s CC:</span> <span className="text-muted">N/A</span></p>
                <p className="text-sm"><span className="font-semibold text-ink">CC3. Helpfulness of the CC in your transaction:</span> <span className="text-muted">N/A</span></p>
              </div>
            ) : (
              <>
                <FeedbackRadioGroup legend="CC2. If aware of CC (answered 1–3 in CC1), would you say that the CC of this office was …?" name="csm-cc2" value={draft.cc2} choices={cc2Choices} onChange={(value) => setDraft((current) => ({ ...current, cc2: value as CSMCC2Value }))} required />
                <FeedbackRadioGroup legend="CC3. If aware of CC (answered codes 1–3 in CC1), how much did the CC help you in your transaction?" name="csm-cc3" value={draft.cc3} choices={cc3Choices} onChange={(value) => setDraft((current) => ({ ...current, cc3: value as CSMCC3Value }))} required />
              </>
            )}
          </FeedbackSection>

          <FeedbackSection title="Service Quality" description="Choose one response for each statement. Not Applicable is an available response and is different from leaving a question unanswered.">
            <div className="space-y-7">
              {sqdQuestions.map(([key, question], index) => <FeedbackRadioGroup key={key} legend={`SQD${index}. ${question}`} name={`csm-${key}`} value={draft.sqds[key] ?? null} choices={sqdChoices} onChange={(value) => setDraft((current) => ({ ...current, sqds: { ...current.sqds, [key]: value as CSMRatingValue } }))} columns={3} required />)}
            </div>
          </FeedbackSection>

          <FeedbackSection title="Suggestions and optional contact">
            <div className="max-w-3xl"><FeedbackFieldLabel htmlFor="csm-suggestions">Suggestions on how we can further improve our services (optional):</FeedbackFieldLabel><Textarea id="csm-suggestions" className="mt-2 min-h-28" value={draft.suggestions} onChange={(event) => setDraft((current) => ({ ...current, suggestions: event.target.value }))} /></div>
            <div className="max-w-xl"><FeedbackFieldLabel htmlFor="csm-email">Email address (optional)</FeedbackFieldLabel><Input id="csm-email" className="mt-2" type="email" autoComplete="email" value={draft.email} onChange={(event) => setDraft((current) => ({ ...current, email: event.target.value }))} /></div>
          </FeedbackSection>
        </fieldset>
        {create.isPending ? <p role="status" aria-live="polite" className="mb-4 text-sm text-muted">Submitting Client Satisfaction Measurement…</p> : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-border pt-5">
          <Button type="submit" disabled={create.isPending || isUncertain}>{create.isPending ? "Submitting…" : "Review and submit"}</Button>
          <Link href="/portal/feedback" className="inline-flex min-h-10 items-center rounded-md px-3 text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Feedback</Link>
        </div>
      </form>
      <AlertDialog open={confirmationOpen} onOpenChange={setConfirmationOpen}>
        <AlertDialogContent>
          <AlertDialogTitle>Submit Client Satisfaction Measurement?</AlertDialogTitle>
          <AlertDialogDescription>Your response will be submitted as a final response. COMPASS does not provide editing or response history after submission.</AlertDialogDescription>
          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <AlertDialogCancel asChild><Button variant="secondary" onClick={() => setPreparedBody(null)}>Review response</Button></AlertDialogCancel>
            <AlertDialogAction asChild><Button disabled={create.isPending} onClick={(event) => { event.preventDefault(); setConfirmationOpen(false); if (preparedBody) void send(preparedBody); }}>{create.isPending ? "Submitting…" : "Submit Client Satisfaction Measurement"}</Button></AlertDialogAction>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
