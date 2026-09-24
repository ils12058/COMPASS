"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import {
  GoodMoralHeading,
  GoodMoralNotice,
  GoodMoralUnavailable,
  goodMoralErrorCode,
  goodMoralErrorMessage,
  uncertainGoodMoralMutation,
} from "@/features/good-moral/good-moral-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  goodMoralCreateMyCurrentStudentRequest,
  goodMoralCreateMyGraduateRequest,
} from "@/lib/api/generated/good-moral/good-moral";
import { getGoodMoralListMyRequestsQueryKey } from "@/lib/api/generated/good-moral/good-moral";
import type { CurrentStudentRequestPayload, GraduateRequestPayload } from "@/lib/api/generated/model";

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
    return <GoodMoralUnavailable title="Request unavailable" message="Your current access does not allow Good Moral request creation." />;
  }

  if (lifecycle === "CURRENT") {
    return <CurrentStudentRequestForm />;
  }
  if (lifecycle === "GRADUATED") {
    return <GraduateRequestForm />;
  }

  return (
    <section className="max-w-2xl space-y-5">
      <GoodMoralHeading title="Good Moral request unavailable" description="A new request is not available for your current Student lifecycle." />
      <p className="text-sm leading-6 text-muted">You can still review your existing Good Moral requests.</p>
      <Link href="/portal/good-moral" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Good Moral</Link>
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
      if (code === "good_moral_conflict") {
        const message = goodMoralErrorMessage(caught, "This Good Moral request conflicts with an existing request.");
        if (/idempotency-key/i.test(message)) {
          intentRef.current = null;
          setUncertainIntent(null);
          setNotice("Review the request details, then submit again deliberately to begin a new request intent.");
        }
      }
      setError(goodMoralErrorMessage(caught, "The Good Moral request could not be created."));
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
    setNotice("Update the details before starting a new request intent. The previous result may still have created a request.");
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
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="max-w-3xl space-y-6">
      <div className="flex flex-col gap-3">
        <Link href="/portal/good-moral" className="inline-flex min-h-9 w-fit items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Good Moral</Link>
        <GoodMoralHeading title={title} description={description} />
      </div>
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
    <div aria-live="polite" className="space-y-3">
      {state.error ? (
        <div role="alert" className="border-y border-danger/30 py-4 text-sm leading-6 text-danger">
          <p>{state.error}</p>
          {state.errorCode === "good_moral_inventory_required" ? (
            <Link href="/portal/inventory/current" className="mt-2 inline-block font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Open Individual Inventory</Link>
          ) : null}
        </div>
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

function CurrentStudentRequestForm() {
  const create = useCreateGoodMoralRequest();
  const [yearLevel, setYearLevel] = useState("");
  const [semester, setSemester] = useState("");
  const fieldsLocked = create.isPending || Boolean(create.uncertainIntent);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.start({ variant: "CURRENT_STUDENT", payload: { year_level: yearLevel, semester } });
  }

  return (
    <RequestFormFrame
      title="Request Current Student certificate"
      description="Enter the year level and semester to record on your request."
    >
      <p className="text-sm leading-6 text-muted">
        Your applicant name, College, course, major, and Academic Year are taken from your current COMPASS records when the request is created.
      </p>
      <CreateFeedback state={create} busy={create.isPending} />
      <form onSubmit={submit} aria-busy={create.isPending} className="max-w-2xl space-y-5">
        <fieldset disabled={fieldsLocked} className="space-y-5 disabled:opacity-80">
          <div>
            <Label htmlFor="good-moral-year-level">Year level <span aria-hidden="true">*</span></Label>
            <Input id="good-moral-year-level" className="mt-2" required maxLength={64} value={yearLevel} onChange={(event) => setYearLevel(event.target.value)} aria-describedby="good-moral-year-level-help" />
            <p id="good-moral-year-level-help" className="mt-1 text-xs text-muted">Up to 64 characters.</p>
          </div>
          <div>
            <Label htmlFor="good-moral-semester">Semester <span aria-hidden="true">*</span></Label>
            <Input id="good-moral-semester" className="mt-2" required maxLength={80} value={semester} onChange={(event) => setSemester(event.target.value)} aria-describedby="good-moral-semester-help" />
            <p id="good-moral-semester-help" className="mt-1 text-xs text-muted">Enter the term wording used for your current enrollment; up to 80 characters.</p>
          </div>
        </fieldset>
        {!create.uncertainIntent ? (
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Submitting request…" : "Submit request"}
          </Button>
        ) : null}
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
    <RequestFormFrame title="Request Graduate certificate" description="Enter the certificate facts for your Graduate Good Moral request.">
      <p className="text-sm leading-6 text-muted">Graduate request details are recorded on this certificate request and are not looked up from your current enrollment records.</p>
      <CreateFeedback state={create} busy={create.isPending} />
      <form onSubmit={submit} aria-busy={create.isPending} className="max-w-2xl space-y-5">
        <fieldset disabled={fieldsLocked} className="space-y-5 disabled:opacity-80">
          <div>
            <Label htmlFor="good-moral-degree">Degree <span aria-hidden="true">*</span></Label>
            <Input id="good-moral-degree" className="mt-2" required maxLength={255} value={degree} onChange={(event) => setDegree(event.target.value)} aria-describedby="good-moral-degree-help" />
            <p id="good-moral-degree-help" className="mt-1 text-xs text-muted">Up to 255 characters.</p>
          </div>
          <div>
            <Label htmlFor="good-moral-major">Major <span className="font-normal text-muted">(optional)</span></Label>
            <Input id="good-moral-major" className="mt-2" maxLength={180} value={major} onChange={(event) => setMajor(event.target.value)} aria-describedby="good-moral-major-help" />
            <p id="good-moral-major-help" className="mt-1 text-xs text-muted">Up to 180 characters.</p>
          </div>
          <div>
            <Label htmlFor="good-moral-graduation-date">Graduation date <span aria-hidden="true">*</span></Label>
            <Input id="good-moral-graduation-date" className="mt-2" type="date" required value={graduationDate} onChange={(event) => setGraduationDate(event.target.value)} />
          </div>
        </fieldset>
        {!create.uncertainIntent ? (
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Submitting request…" : "Submit request"}
          </Button>
        ) : null}
      </form>
    </RequestFormFrame>
  );
}
