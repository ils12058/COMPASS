"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { useExitInterviewsGetMyStatus } from "@/lib/api/generated/exit-interviews/exit-interviews";
import { GraduationGoodMoralPrerequisite } from "@/features/good-moral/graduation-good-moral-prerequisite";
import { GoodMoralDegreeInput } from "@/features/good-moral/good-moral-degree-input";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import {
  GOOD_MORAL_SEMESTERS,
  GoodMoralHeading,
  GoodMoralNotice,
  GoodMoralUnavailable,
  goodMoralErrorCode,
  goodMoralErrorMessage,
  uncertainGoodMoralMutation,
} from "@/features/good-moral/good-moral-shared";
import { useGoodMoralGetMyF4AcademicContext } from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralF4AcademicContextResponse, GoodMoralF4EligibilityStatus } from "@/lib/api/generated/model";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  goodMoralCreateMyCurrentStudentRequest,
  goodMoralCreateMyGraduateRequest,
} from "@/lib/api/generated/good-moral/good-moral";
import { getGoodMoralListMyRequestsQueryKey } from "@/lib/api/generated/good-moral/good-moral";
import type { CurrentStudentRequestPayload, GraduateRequestPayload } from "@/lib/api/generated/model";
import { institutionalDateInputValue } from "@/lib/institutional-time";

type CreateIntent =
  | {
      variant: "CURRENT_STUDENT";
      payload: CurrentStudentRequestPayload;
      fingerprint: string;
      key: string;
    }
  | {
      variant: "GRADUATE";
      payload: GraduateRequestPayload;
      fingerprint: string;
      key: string;
    };

type CreateFormInput =
  | { variant: "CURRENT_STUDENT"; payload: CurrentStudentRequestPayload }
  | { variant: "GRADUATE"; payload: GraduateRequestPayload };

export function GoodMoralRequestPage() {
  const { user } = usePortalSession();
  const access = getGoodMoralAccess(user);
  const lifecycle = user.student_lifecycle_status;

  if (!access.isStudent || !access.canRequestSelf) {
    return <GoodMoralUnavailable title="Request unavailable" message="You cannot submit a Good Moral request with this account." />;
  }

  if (lifecycle === "CURRENT") {
    return <CurrentStudentRequestChoices />;
  }
  if (lifecycle === "GRADUATED" || lifecycle === "FORMER") {
    return <GraduateRequestForm />;
  }

  return (
    <section className="max-w-2xl space-y-5">
      <GoodMoralHeading title="Good Moral request unavailable" description="A new request needs an active Student account with a recorded lifecycle status." />
      <Notice action={<Link href="/portal/good-moral" className={buttonVariants({ variant: "secondary" })}>Back to Good Moral</Link>}>
        You can still review your existing Good Moral requests.
      </Notice>
    </section>
  );
}

function useCreateGoodMoralRequest() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const intentRef = useRef<{ fingerprint: string; key: string } | null>(null);
  const [uncertainIntent, setUncertainIntent] = useState<CreateIntent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | undefined>();
  const [notice, setNotice] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: (intent: CreateIntent) =>
      intent.variant === "CURRENT_STUDENT"
        ? goodMoralCreateMyCurrentStudentRequest(intent.payload, {
            headers: { "Idempotency-Key": intent.key },
          })
        : goodMoralCreateMyGraduateRequest(intent.payload, {
            headers: { "Idempotency-Key": intent.key },
          }),
    retry: false,
  });

  async function send(intent: CreateIntent) {
    setError(null);
    setErrorCode(undefined);
    setNotice(null);
    try {
      const response = await create.mutateAsync(intent);
      intentRef.current = null;
      setUncertainIntent(null);
      await queryClient.invalidateQueries({ queryKey: getGoodMoralListMyRequestsQueryKey() });
      router.push(`/portal/good-moral/${response.data.id}`);
    } catch (caught) {
      const code = goodMoralErrorCode(caught);
      setErrorCode(code);
      if (code === "idempotency_key_conflict") {
        // The details changed after an uncertain attempt; the next submit starts a new request.
        intentRef.current = null;
        setUncertainIntent(null);
        setNotice("Review the request details, then submit again to start a new request.");
      }
      setError(goodMoralErrorMessage(caught, uncertainGoodMoralMutation(caught)
        ? "The request result could not be confirmed. Retry the same request to check whether it was received."
        : "The Good Moral request could not be created."));
      if (uncertainGoodMoralMutation(caught)) {
        setUncertainIntent(intent);
      } else {
        setUncertainIntent(null);
      }
    }
  }

  function start(input: CreateFormInput) {
    setError(null);
    setErrorCode(undefined);
    setNotice(null);
    if (!globalThis.crypto?.randomUUID) {
      setError("This browser cannot create a secure request identity. Update the browser and try again.");
      return;
    }
    const fingerprint = `${input.variant}\0${JSON.stringify(input.payload)}`;
    const key = intentRef.current?.fingerprint === fingerprint
      ? intentRef.current.key
      : globalThis.crypto.randomUUID();
    intentRef.current = { fingerprint, key };
    if (input.variant === "CURRENT_STUDENT") {
      void send({ ...input, fingerprint, key });
    } else {
      void send({ ...input, fingerprint, key });
    }
  }

  function retrySameRequest() {
    if (uncertainIntent) void send(uncertainIntent);
  }

  function startNewIntent() {
    intentRef.current = null;
    setUncertainIntent(null);
    setError(null);
    setNotice("Update the details before submitting again. The previous attempt may already have created a request.");
  }

  return {
    start,
    retrySameRequest,
    startNewIntent,
    isPending: create.isPending,
    error,
    errorCode,
    notice,
    uncertainIntent,
    setError,
  };
}

function RequestFormFrame({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="max-w-3xl space-y-5">
      <GoodMoralHeading
        title={title}
        description={description}
        back={<Link href="/portal/good-moral" className={pageBackLinkClass}>Back to Good Moral</Link>}
      />
      {children}
    </section>
  );
}

function CreateFeedback({
  state,
  busy,
}: {
  state: ReturnType<typeof useCreateGoodMoralRequest>;
  busy: boolean;
}) {
  return (
    <div className="space-y-3">
      {state.error ? (
        <Notice
          role="alert"
          tone="danger"
          action={state.errorCode === "good_moral_inventory_required" ? (
            <Link href="/portal/inventory/current" className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Open Individual Inventory</Link>
          ) : state.errorCode === "good_moral_exit_interview_required" ? (
            <Link href="/portal/exit-interviews" className={buttonVariants({ variant: "secondary" })}>Open Exit Interview</Link>
          ) : undefined}
        >
          {state.error}
        </Notice>
      ) : null}
      {state.notice ? <GoodMoralNotice>{state.notice}</GoodMoralNotice> : null}
      {state.uncertainIntent ? (
        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" onClick={state.retrySameRequest} disabled={busy}>Retry same request</Button>
          <Button variant="quiet" onClick={state.startNewIntent} disabled={busy}>Edit details instead</Button>
        </div>
      ) : null}
    </div>
  );
}

function f4YearLevelLabel(value: number | null | undefined): string | null {
  return value === 1 ? "1st Year" : value === 2 ? "2nd Year" : value === 3 ? "3rd Year" : value === 4 ? "4th Year" : null;
}

function f4EligibilityMessage(status: GoodMoralF4EligibilityStatus): string {
  switch (status) {
    case "NOT_CURRENT": return "F4 is for current students. This account is not currently marked as a Current Student.";
    case "INVENTORY_REQUIRED": return "Submit the Individual Inventory for the current Academic Year before requesting F4.";
    case "UNCLASSIFIED_PROGRAM": return "The Program on the submitted Inventory is not classified. Contact the Guidance Office to confirm your Program before requesting F4.";
    case "POSTGRADUATE_PROGRAM": return "F4 is for current Bachelor's students. COMPASS does not currently offer an approved postgraduate Good Moral form.";
    case "UNSUPPORTED_YEAR_LEVEL": return "The submitted Inventory does not contain a supported 1st–4th Year Level for this Bachelor's Program. Correct the Inventory or contact the Guidance Office.";
    case "ELIGIBLE": return "Your Program and Year Level meet the current F4 academic requirements.";
  }
}

function CurrentStudentRequestChoices() {
  const context = useGoodMoralGetMyF4AcademicContext({ query: { retry: false, refetchOnWindowFocus: true, staleTime: 0 } });
  const [variant, setVariant] = useState<"CURRENT_STUDENT" | "GRADUATE">("CURRENT_STUDENT");
  const academicContext = context.data?.data;
  const f4Eligible = academicContext?.status === "ELIGIBLE" && f4YearLevelLabel(academicContext.year_level) !== null;

  return (
    <section className="max-w-3xl space-y-5">
      <GoodMoralHeading title="Request Good Moral Certificate" description="Choose the request that matches the certificate you need." back={<Link href="/portal/good-moral" className={pageBackLinkClass}>Back to Good Moral</Link>} />
      <Panel as="div">
        <PanelSection title="Certificate type" titleId="good-moral-certificate-type" description="F4 is for current Bachelor's students. F6 is for a previously completed UCN Bachelor's degree, even if you later enrolled in postgraduate studies.">
          {context.isPending ? <LoadingRegion label="Checking current Inventory Program and Year Level…"><Skeleton className="h-14 w-full" /></LoadingRegion> : null}
          {context.isError ? <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void context.refetch()}>Retry</Button>}>F4 eligibility could not be confirmed. You can still choose F6 if you are requesting it for a previously completed UCN Bachelor&apos;s degree.</Notice> : null}
          {academicContext && !f4Eligible ? <Notice>{f4EligibilityMessage(academicContext.status)}</Notice> : null}
          <div className="mt-4 flex flex-wrap gap-3" role="group" aria-label="Good Moral certificate type">
            <Button type="button" variant={variant === "CURRENT_STUDENT" ? "primary" : "secondary"} aria-pressed={variant === "CURRENT_STUDENT"} disabled={!f4Eligible} onClick={() => setVariant("CURRENT_STUDENT")}>F4 · Current Student</Button>
            <Button type="button" variant={variant === "GRADUATE" ? "primary" : "secondary"} aria-pressed={variant === "GRADUATE"} onClick={() => setVariant("GRADUATE")}>F6 · Undergraduate alumnus</Button>
          </div>
        </PanelSection>
      </Panel>
      {variant === "CURRENT_STUDENT" && f4Eligible && academicContext ? <CurrentStudentRequestForm academicContext={academicContext} /> : null}
      {variant === "GRADUATE" ? <GraduateRequestForm /> : null}
    </section>
  );
}

function CurrentStudentRequestForm({ academicContext }: { academicContext: GoodMoralF4AcademicContextResponse }) {
  const { user } = usePortalSession();
  const canReadExitStatus = user.capabilities.includes("exit_interviews.view_self");
  const status = useExitInterviewsGetMyStatus({ query: { enabled: canReadExitStatus, retry: false, refetchOnWindowFocus: true, staleTime: 0 } });
  const blocked = canReadExitStatus && (status.isPending || status.isError || status.data?.data.graduation_good_moral_blocked === true);
  const create = useCreateGoodMoralRequest();
  const [semester, setSemester] = useState("");
  const fieldsLocked = create.isPending || Boolean(create.uncertainIntent) || blocked;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (blocked || !academicContext.year_level || !semester) return;
    create.start({ variant: "CURRENT_STUDENT", payload: { semester } });
  }

  return (
    <RequestFormFrame
      title="F4 · Current Student request"
      description="F4 is for a current Student whose submitted Inventory has a classified Bachelor's Program and supported Year Level."
    >
      <CreateFeedback state={create} busy={create.isPending} />
      {canReadExitStatus && status.isPending ? <LoadingRegion label="Checking Good Moral prerequisites…"><Skeleton className="h-14 w-full" /></LoadingRegion> : canReadExitStatus && status.isError ? (
        <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void status.refetch()}>Retry</Button>}>Your graduation workflow status could not be confirmed.</Notice>
      ) : status.data?.data.graduation_good_moral_blocked ? <GraduationGoodMoralPrerequisite /> : null}
      <form onSubmit={submit} aria-busy={create.isPending}>
        <Panel as="div">
        <PanelSection
          title="Request details"
          titleId="good-moral-current-request-details"
          description="Your applicant name, College, course, major, and Academic Year are taken from your current COMPASS records when the request is created."
        >
        <fieldset disabled={fieldsLocked} className="max-w-2xl space-y-5 disabled:opacity-80">
          <div>
            <Label htmlFor="good-moral-year-level">Year Level</Label>
            <Input id="good-moral-year-level" className="mt-2" value={f4YearLevelLabel(academicContext.year_level) ?? ""} readOnly aria-describedby="good-moral-year-level-help" />
            <p id="good-moral-year-level-help" className="mt-1 text-xs text-muted">Taken from your submitted Individual Inventory. It cannot be changed on this form.</p>
          </div>
          <div>
            <Label htmlFor="good-moral-semester">Semester <span aria-hidden="true">*</span></Label>
            <Select
              id="good-moral-semester"
              className="mt-2"
              required
              value={semester}
              onChange={(event) => setSemester(event.target.value)}
            >
              <option value="">Select your Semester</option>
              {GOOD_MORAL_SEMESTERS.map((sem) => (
                <option key={sem} value={sem}>{sem}</option>
              ))}
            </Select>
          </div>
        </fieldset>
        </PanelSection>
        {!create.uncertainIntent ? (
          <PanelFooter>
            <Button type="submit" disabled={create.isPending || blocked}>
              {create.isPending ? "Submitting request…" : "Submit request"}
            </Button>
          </PanelFooter>
        ) : null}
        </Panel>
      </form>
    </RequestFormFrame>
  );
}

function GraduateRequestForm() {
  const create = useCreateGoodMoralRequest();
  const [degree, setDegree] = useState("");
  const [major, setMajor] = useState("");
  const [graduationDate, setGraduationDate] = useState("");
  const fieldsLocked = create.isPending || Boolean(create.uncertainIntent);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.start({ variant: "GRADUATE", payload: { degree, major, graduation_date: graduationDate } });
  }

  return (
    <RequestFormFrame title="F6 · Undergraduate alumnus request">
      <CreateFeedback state={create} busy={create.isPending} />
      <Notice>
        F6 is for a previously completed UCN Bachelor&apos;s degree. The degree and graduation date below are self-reported; COMPASS does not verify degree completion. A current or postgraduate enrollment record does not establish that a Bachelor&apos;s degree was completed.
      </Notice>
      <form onSubmit={submit} aria-busy={create.isPending}>
        <Panel as="div">
        <PanelSection
          title="Graduation details"
          titleId="good-moral-graduate-request-details"
          description="Enter the UCN Bachelor's degree for which you are requesting F6, including a historical program that is no longer listed."
        >
        <fieldset disabled={fieldsLocked} className="max-w-2xl space-y-5 disabled:opacity-80">
          <GoodMoralDegreeInput id="good-moral-degree" value={degree} onChange={setDegree} disabled={fieldsLocked} />
          <div>
            <Label htmlFor="good-moral-major">Major <span className="font-normal text-muted">(optional)</span></Label>
            <Input id="good-moral-major" className="mt-2" maxLength={180} value={major} onChange={(event) => setMajor(event.target.value)} aria-describedby="good-moral-major-help" />
            <p id="good-moral-major-help" className="mt-1 text-xs text-muted">Up to 180 characters.</p>
          </div>
          <div>
            <Label htmlFor="good-moral-graduation-date">Graduation date <span aria-hidden="true">*</span></Label>
            <Input id="good-moral-graduation-date" className="mt-2" type="date" required max={institutionalDateInputValue()} value={graduationDate} onChange={(event) => setGraduationDate(event.target.value)} />
          </div>
        </fieldset>
        </PanelSection>
        {!create.uncertainIntent ? (
          <PanelFooter>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Submitting request…" : "Submit request"}
            </Button>
          </PanelFooter>
        ) : null}
        </Panel>
      </form>
    </RequestFormFrame>
  );
}
