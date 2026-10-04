"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
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
    return <GoodMoralUnavailable title="Request unavailable" message="You cannot submit a Good Moral request with this account." />;
  }

  if (lifecycle === "CURRENT") {
    return <CurrentStudentRequestForm />;
  }
  if (lifecycle === "GRADUATED") {
    return <GraduateRequestForm />;
  }

  return (
    <section className="max-w-2xl space-y-5">
      <GoodMoralHeading title="Good Moral request unavailable" description="A new request is available only to current students and graduates." />
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
      title="Request Good Moral Certificate"
    >
      <CreateFeedback state={create} busy={create.isPending} />
      <form onSubmit={submit} aria-busy={create.isPending}>
        <Panel as="div">
        <PanelSection
          title="Request details"
          titleId="good-moral-current-request-details"
          description="Your applicant name, College, course, major, and Academic Year are taken from your current COMPASS records when the request is created."
        >
        <fieldset disabled={fieldsLocked} className="max-w-2xl space-y-5 disabled:opacity-80">
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
    <RequestFormFrame title="Request Good Moral Certificate">
      <CreateFeedback state={create} busy={create.isPending} />
      <form onSubmit={submit} aria-busy={create.isPending}>
        <Panel as="div">
        <PanelSection
          title="Graduation details"
          titleId="good-moral-graduate-request-details"
          description="These details will be recorded on your request rather than taken from current enrollment records."
        >
        <fieldset disabled={fieldsLocked} className="max-w-2xl space-y-5 disabled:opacity-80">
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
