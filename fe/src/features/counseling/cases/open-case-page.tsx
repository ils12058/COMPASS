"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter, PanelHeader, PanelMessage, PanelSection } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import {
  caseErrorCode,
  caseErrorMessage,
  caseHref,
  caseOriginLabel,
  CASES_PATH,
  isUncertainCaseResult,
  sessionCountLabel,
} from "@/features/counseling/cases/case-presentation";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorMessage,
  CounselingPageHeading,
  CounselingUnavailable,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getCounselingListMyCasesQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingGetCaseOpeningContext,
  useCounselingListStudents,
  useCounselingOpenCase,
} from "@/lib/api/generated/counseling/counseling";
import { CounselingCaseOrigin } from "@/lib/api/generated/model";

const textLink = "font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
const backLink = <Link href={CASES_PATH} className={pageBackLinkClass}>Back to Counseling</Link>;

function readOrigin(value: string | null): CounselingCaseOrigin {
  return value && (Object.values(CounselingCaseOrigin) as string[]).includes(value)
    ? (value as CounselingCaseOrigin)
    : CounselingCaseOrigin.INTAKE;
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="min-w-0"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm text-ink">{children}</dd></div>;
}

// A Counseling intake has no source record, so the Counselor chooses the Student through the
// Counseling Student search, the same one used to record a walk-in.
function StudentChooser({ onChoose }: { onChoose: (studentId: string) => void }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const students = useCounselingListStudents(
    { ...(query ? { search: query } : {}), page, page_size: 10 },
    { query: { retry: false } },
  );
  const items = students.data?.data.items ?? [];

  return (
    <Panel aria-labelledby="open-case-student-heading">
      <PanelHeader title="Choose the Student" titleId="open-case-student-heading" />
      <PanelBody className="space-y-4">
        <form className="grid gap-2 sm:max-w-xl" role="search" aria-label="Students" onSubmit={(event: FormEvent) => { event.preventDefault(); setQuery(search.trim()); setPage(1); }}>
          <Label htmlFor="open-case-student-search">Search for a Student</Label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input id="open-case-student-search" value={search} maxLength={160} onChange={(event) => setSearch(event.target.value)} placeholder="Student name or Institutional ID" />
            <Button type="submit" variant="secondary">Search</Button>
          </div>
        </form>
        {students.isPending ? (
          <div aria-busy="true" className="space-y-2"><span className="sr-only">Loading Students…</span><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /></div>
        ) : students.isError ? (
          <div role="alert"><p className="text-sm text-danger">{counselingErrorMessage(students.error, "Couldn't load Students.")}</p><Button variant="secondary" className="mt-3" onClick={() => void students.refetch()}>Retry</Button></div>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted">No Students match this search.</p>
        ) : (
          <>
            <ul className="divide-y divide-border rounded-sm border border-border" aria-label="Students">
              {items.map((student) => (
                <li key={student.id}>
                  <button type="button" onClick={() => onChoose(student.id)} className="w-full px-4 py-3 text-left transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus">
                    <span className="flex items-center gap-2 font-semibold text-ink"><PersonAvatar displayName={student.display_name} photoUrl={student.profile_photo_url} photoUpdatedAt={student.profile_photo_updated_at} size="compact" />{student.display_name}</span>
                    <span className="mt-1 block text-sm text-muted">Institutional ID: {student.institutional_id ?? "Not provided"}</span>
                  </button>
                </li>
              ))}
            </ul>
            <CanonicalPagination className="border-t-0 pb-0" label="Student pages" page={students.data?.data.page ?? page} hasNext={students.data?.data.has_next ?? false} onPageChange={setPage} />
          </>
        )}
      </PanelBody>
    </Panel>
  );
}

export function OpenCasePage() {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const origin = readOrigin(searchParams.get("origin"));
  const sourceId = searchParams.get("source") ?? "";
  const studentId = searchParams.get("student") ?? "";
  const intake = origin === CounselingCaseOrigin.INTAKE;
  const ready = intake ? Boolean(studentId) : Boolean(sourceId);
  const allowed = access.isCounselor && access.canManageAssigned;
  const context = useCounselingGetCaseOpeningContext(
    { origin, ...(intake ? { student_id: studentId } : { source_id: sourceId }) },
    { query: { enabled: allowed && ready, retry: false, staleTime: 0 } },
  );
  const open = useCounselingOpenCase({ mutation: { retry: false } });
  const [error, setError] = useState<string | null>(null);
  const [reviewAgain, setReviewAgain] = useState(false);
  const [uncertain, setUncertain] = useState(false);

  if (!allowed) return <CounselingUnavailable title="Open case">You don&apos;t have access to open Counseling cases.</CounselingUnavailable>;

  const heading = <CounselingPageHeading title="Open case" back={backLink} />;

  if (!ready) {
    if (!intake) {
      return <>{heading}<Notice role="alert" tone="danger" action={<Link href={CASES_PATH} className={buttonVariants({ variant: "secondary" })}>Back to Counseling</Link>}>Open a case from one of your Appointments, recorded sessions or Routine Interviews, or choose a Student from Counseling.</Notice></>;
    }
    return <>{heading}<StudentChooser onChoose={(id) => router.replace(`${pathname}?student=${encodeURIComponent(id)}`, { scroll: false })} /></>;
  }

  if (context.isPending) {
    return <>{heading}<Panel as="div" aria-busy="true"><PanelBody><span className="sr-only">Loading case details…</span><Skeleton className="h-6 w-1/2" /><Skeleton className="mt-4 h-24 w-full" /></PanelBody></Panel></>;
  }
  if (context.isError || !context.data) {
    return (
      <>
        {heading}
        <Notice
          role="alert"
          tone="danger"
          action={<>
            {caseErrorCode(context.error) ? null : <Button variant="secondary" onClick={() => void context.refetch()}>Retry</Button>}
            {intake ? <Button variant="secondary" onClick={() => router.replace(pathname, { scroll: false })}>Choose another Student</Button> : null}
          </>}
        >
          {caseErrorMessage(context.error, "Couldn't load the details for this case. Try again.")}
        </Notice>
      </>
    );
  }

  const details = context.data.data;
  const active = details.active_cases;
  const submitting = open.isPending;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || uncertain) return;
    setError(null);
    setReviewAgain(false);
    try {
      const response = await open.mutateAsync({
        data: {
          origin,
          ...(intake ? { student_id: details.student.id } : { source_id: sourceId }),
          known_active_case_ids: active.map((item) => item.id),
        },
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getCounselingListMyCasesQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
      ]);
      router.replace(caseHref(response.data.id));
    } catch (caught) {
      if (isUncertainCaseResult(caught)) {
        setUncertain(true);
        return;
      }
      if (caseErrorCode(caught) === "counseling_case_review_required") {
        // The active cases shown are no longer current: load them again for a deliberate review.
        setReviewAgain(true);
        await context.refetch();
        return;
      }
      setError(caseErrorMessage(caught, "The case couldn't be opened. Review the details and try again."));
    }
  }

  return (
    <>
      {heading}
      <form onSubmit={submit} noValidate>
        <Panel as="div">
          <dl className="grid gap-x-8 gap-y-4 px-4 py-4 sm:grid-cols-2 sm:px-5">
            <Fact label="Student">
              <span className="inline-flex items-center gap-2"><PersonAvatar displayName={details.student.display_name} photoUrl={details.student.profile_photo_url} photoUpdatedAt={details.student.profile_photo_updated_at} size="compact" /><span className="font-semibold">{details.student.display_name}</span></span>
              <span className="mt-1 block text-xs text-muted">Institutional ID: {details.student.institutional_id ?? "Not provided"}</span>
            </Fact>
            <Fact label="Responsible counselor">You</Fact>
            <Fact label="Starts from">
              {caseOriginLabel(details.origin)}
              {details.source.appointment ? <> {details.source.appointment.reference_code} · {formatCounselingDateTime(details.source.appointment.starts_at)}</> : null}
            </Fact>
            <Fact label="Session included">
              {details.session
                ? <>{formatCounselingDateTime(details.session.started_at)} – {formatCounselingDateTime(details.session.ended_at)} · {counselingEntryModeLabel(details.session.entry_mode)} · {counselingDeliveryModeLabel(details.session.delivery_mode)}</>
                : "None yet"}
            </Fact>
          </dl>

          <PanelSection title="Your active cases with this Student" titleId="open-case-active-heading" description={active.length > 0 ? "Open another case only for a different concern. To continue one of these, open it and add the session there." : undefined}>
            {reviewAgain ? <p role="status" className="mb-3 text-sm text-warning">Your active cases for this Student changed. Review them before opening a case.</p> : null}
            {active.length === 0 ? (
              <p className="text-sm text-muted">None. This will be your first active case with this Student.</p>
            ) : (
              <ul className="divide-y divide-border rounded-sm border border-border">
                {active.map((item) => (
                  <li key={item.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3">
                    <Link href={caseHref(item.id)} className={textLink}>{item.reference_code}</Link>
                    <span className="text-sm text-muted">Opened {formatCounselingDateTime(item.opened_at)} · {sessionCountLabel(item.session_count)}</span>
                  </li>
                ))}
              </ul>
            )}
          </PanelSection>

          {error ? <PanelMessage role="alert" tone="danger" density="compact">{error}</PanelMessage> : null}
          {uncertain ? (
            <Notice role="alert" tone="warning" className="mx-4 mb-4 sm:mx-5" action={<Link href={CASES_PATH} className={buttonVariants({ variant: "secondary" })}>Check my cases</Link>}>
              <p className="text-ink">Couldn&apos;t confirm whether the case was opened. Check your cases before trying again to avoid a duplicate.</p>
            </Notice>
          ) : (
            <PanelFooter>
              <Button type="submit" disabled={submitting} aria-busy={submitting}>{submitting ? "Opening case…" : active.length > 0 ? "Open another case" : "Open case"}</Button>
              <Link href={CASES_PATH} aria-disabled={submitting} className={buttonVariants({ variant: "secondary" })}>Cancel</Link>
              {intake ? <Button variant="quiet" disabled={submitting} onClick={() => router.replace(pathname, { scroll: false })}>Choose another Student</Button> : null}
            </PanelFooter>
          )}
        </Panel>
      </form>
    </>
  );
}
