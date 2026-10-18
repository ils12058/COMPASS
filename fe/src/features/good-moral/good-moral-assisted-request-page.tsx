"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { GoodMoralDegreeInput } from "@/features/good-moral/good-moral-degree-input";
import { GOOD_MORAL_SEMESTERS, GoodMoralHeading, GoodMoralUnavailable, formatGoodMoralDate, goodMoralVariantLabel, uncertainGoodMoralMutation } from "@/features/good-moral/good-moral-shared";
import { EligibleStudentPicker } from "@/features/portal/components/eligible-student-picker";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { goodMoralCreateAssistedCurrentStudentRequest, goodMoralCreateAssistedGraduateRequest, getGoodMoralListRequestsQueryKey, useGoodMoralListEligibleStudents } from "@/lib/api/generated/good-moral/good-moral";
import type { AssistedCurrentStudentRequestPayload, AssistedGraduateRequestPayload, GoodMoralStudentOptionResponse } from "@/lib/api/generated/model";
import { getWorkQueueListQueryKey } from "@/lib/api/generated/work/work";
import { getOverviewGetSummaryQueryKey } from "@/lib/api/generated/overview/overview";
import { institutionalDateInputValue } from "@/lib/institutional-time";
import { assistedCreationError } from "@/features/good-moral/good-moral-assisted-request";

type Intent = { key: string } & (
  | { variant: "CURRENT_STUDENT"; payload: AssistedCurrentStudentRequestPayload }
  | { variant: "GRADUATE"; payload: AssistedGraduateRequestPayload }
);

export function GoodMoralAssistedRequestPage() {
  const { user } = usePortalSession();
  if (!getGoodMoralAccess(user).canInitiate) return <GoodMoralUnavailable title="Request initiation unavailable" message="You cannot start a Good Moral request for a Student with this account." />;
  return <AssistedRequestForm />;
}

function AssistedRequestForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [student, setStudent] = useState<GoodMoralStudentOptionResponse | null>(null);
  const [variant, setVariant] = useState<"CURRENT_STUDENT" | "GRADUATE">("CURRENT_STUDENT");
  const [semester, setSemester] = useState("");
  const [degree, setDegree] = useState("");
  const [major, setMajor] = useState("");
  const [graduationDate, setGraduationDate] = useState("");
  const [intent, setIntent] = useState<Intent | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const sending = useRef(false);
  const reviewButton = useRef<HTMLButtonElement>(null);
  const students = useGoodMoralListEligibleStudents({ search: appliedSearch, page, page_size: 10 }, { query: { retry: false } });
  const creation = useMutation({
    mutationFn: (value: Intent) => value.variant === "CURRENT_STUDENT"
      ? goodMoralCreateAssistedCurrentStudentRequest(value.payload, { headers: { "Idempotency-Key": value.key } })
      : goodMoralCreateAssistedGraduateRequest(value.payload, { headers: { "Idempotency-Key": value.key } }),
    retry: false,
  });
  const locked = creation.isPending || uncertain || Boolean(createdId);

  function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!student || locked) return;
    const payload = variant === "CURRENT_STUDENT"
      ? { variant, payload: { student_id: student.id, semester } }
      : { variant, payload: { student_id: student.id, degree, major, graduation_date: graduationDate } };
    // Reopening an unchanged review preserves its creation identity, including known failures.
    if (!intent || JSON.stringify({ variant: intent.variant, payload: intent.payload }) !== JSON.stringify(payload)) {
      setIntent({ ...payload, key: crypto.randomUUID() });
    }
    setError(null);
    setReviewOpen(true);
  }

  async function send() {
    if (!intent || sending.current || createdId) return;
    sending.current = true;
    setError(null);
    try {
      const response = await creation.mutateAsync(intent);
      setCreatedId(response.data.id);
      setUncertain(false);
      // Refetch the queue and the existing portal work indicators when they next mount.
      void queryClient.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() });
      void queryClient.invalidateQueries({ queryKey: getWorkQueueListQueryKey() });
      void queryClient.invalidateQueries({ queryKey: getOverviewGetSummaryQueryKey() });
    } catch (caught) {
      setUncertain(uncertainGoodMoralMutation(caught));
      setError(assistedCreationError(caught));
    } finally {
      sending.current = false;
    }
  }

  function closeReview(open: boolean) {
    if (!open && createdId) router.push(`/portal/good-moral/${createdId}`);
    setReviewOpen(open);
  }

  return (
    <section className="space-y-5">
      <GoodMoralHeading title="Start request for Student" description="F4 is available only for a current Bachelor's Student whose submitted Inventory is classified. F6 records a Student-reported UCN undergraduate degree and does not verify completion." back={<Link href="/portal/good-moral" className={pageBackLinkClass}>Back to Good Moral</Link>} />
      <Panel as="div">
        <PanelSection title="Student" titleId="assisted-student-heading">
          <fieldset disabled={locked} className="min-w-0">
            <EligibleStudentPicker
              search={search} onSearchChange={setSearch}
              onSearch={() => { setStudent(null); setIntent(null); if (appliedSearch === search.trim() && page === 1) void students.refetch(); setAppliedSearch(search.trim()); setPage(1); }}
              items={students.data?.data.items ?? []} selectedStudent={student} selectedId={student?.id ?? null}
              label="Student for Good Moral request"
              optionDescription={(option) => {
                const goodMoralOption = option as GoodMoralStudentOptionResponse;
                if (goodMoralOption.id !== student?.id || goodMoralOption.variant !== "CURRENT_STUDENT") return goodMoralOption.variant === "GRADUATE" ? "F6 · Undergraduate alumnus request" : "Select to review F4 academic eligibility or prepare an F6 alumni request.";
                const context = goodMoralOption.f4_eligibility;
                if (context?.status === "ELIGIBLE") return `F4 available · ${context.year_level ? `${context.year_level}${context.year_level === 1 ? "st" : context.year_level === 2 ? "nd" : context.year_level === 3 ? "rd" : "th"} Year` : "Bachelor's Program"}; F6 can also be selected as a student-reported claim.`;
                if (context?.status === "POSTGRADUATE_PROGRAM") return "F4 unavailable · postgraduate Program. F6 can be requested for a Student-reported, previously completed UCN Bachelor's degree; COMPASS does not verify completion.";
                if (context?.status === "UNCLASSIFIED_PROGRAM") return "F4 unavailable · Program is unclassified. Contact the Guidance Office. F6 remains a student-reported claim.";
                return "F4 unavailable · current Inventory eligibility is not confirmed. F6 remains a student-reported claim.";
              }}
              onSelect={(selected) => {
                // Only the verified options from this endpoint determine the variant.
                const option = students.data?.data.items.find((item) => item.id === selected.id);
                if (option) { setStudent(option); setVariant(option.variant === "CURRENT_STUDENT" && option.f4_eligibility?.status === "ELIGIBLE" ? "CURRENT_STUDENT" : "GRADUATE"); setIntent(null); setError(null); setSemester(""); setDegree(""); setMajor(""); setGraduationDate(""); }
              }}
              page={students.data?.data.page ?? page} hasNext={students.data?.data.has_next ?? false}
              isLoading={students.isPending || students.isFetching} isError={students.isError}
              errorMessage="Students could not be loaded. Retry the search."
              onRetry={() => void students.refetch()} onPageChange={setPage}
            />
          </fieldset>
        </PanelSection>
        {student ? (
          <PanelSection title="Certificate type" titleId="assisted-good-moral-certificate-type">
            <Label htmlFor="assisted-good-moral-variant">Request type <span aria-hidden="true">*</span></Label>
            <Select id="assisted-good-moral-variant" className="mt-2 max-w-xl" value={variant} onChange={(event) => { setVariant(event.target.value as "CURRENT_STUDENT" | "GRADUATE"); setIntent(null); }} disabled={locked}>
              <option value="CURRENT_STUDENT" disabled={student.variant !== "CURRENT_STUDENT" || student.f4_eligibility?.status !== "ELIGIBLE"}>F4 · Current Student</option>
              <option value="GRADUATE">F6 · Undergraduate alumnus</option>
            </Select>
            {variant === "CURRENT_STUDENT" ? <p className="mt-2 text-sm text-muted">F4 eligibility is based on the linked submitted Inventory Program and Year Level.</p> : <p className="mt-2 text-sm text-muted">F6 degree and graduation date are Student-reported. COMPASS does not verify degree completion; current or postgraduate enrollment is not proof of a completed UCN Bachelor&apos;s degree.</p>}
          </PanelSection>
        ) : null}
        {student ? (
          <form onSubmit={review} aria-busy={creation.isPending}>
            <PanelSection title={`${goodMoralVariantLabel(variant)} request details`} titleId="assisted-request-details">
              <fieldset disabled={locked} className="grid gap-5 sm:grid-cols-2">
                {variant === "CURRENT_STUDENT" ? <>
                  <div><Label htmlFor="assisted-year">Year level</Label>
                    <Input id="assisted-year" className="mt-2" value={student.f4_eligibility?.year_level ? `${student.f4_eligibility.year_level}${student.f4_eligibility.year_level === 1 ? "st" : student.f4_eligibility.year_level === 2 ? "nd" : student.f4_eligibility.year_level === 3 ? "rd" : "th"} Year` : ""} readOnly aria-describedby="assisted-year-help" />
                    <p id="assisted-year-help" className="mt-1 text-xs text-muted">Taken from the submitted Individual Inventory.</p></div>
                  <div><Label htmlFor="assisted-semester">Semester <span aria-hidden="true">*</span></Label>
                    <Select id="assisted-semester" className="mt-2" required value={semester} onChange={(event) => setSemester(event.target.value)}>
                      <option value="">Select semester</option>{GOOD_MORAL_SEMESTERS.map((value) => <option key={value}>{value}</option>)}
                    </Select></div>
                </> : <>
                  <GoodMoralDegreeInput id="assisted-degree" value={degree} onChange={setDegree} disabled={locked} label="Student-reported degree" />
                  <div><Label htmlFor="assisted-major">Major (optional)</Label><Input id="assisted-major" className="mt-2" maxLength={180} value={major} onChange={(event) => setMajor(event.target.value)} /></div>
                  <div><Label htmlFor="assisted-graduation">Graduation date <span aria-hidden="true">*</span></Label><Input id="assisted-graduation" className="mt-2" type="date" required max={institutionalDateInputValue()} value={graduationDate} onChange={(event) => setGraduationDate(event.target.value)} /></div>
                </>}
              </fieldset>
            </PanelSection>
            <PanelFooter>
              {uncertain ? <Button ref={reviewButton} onClick={() => setReviewOpen(true)}>Retry same request</Button> : <Button ref={reviewButton} type="submit" disabled={locked}>Review request</Button>}
            </PanelFooter>
          </form>
        ) : null}
      </Panel>
      <ConsequentialActionDialog open={reviewOpen} onOpenChange={closeReview} title="Start Good Moral request?"
        confirmLabel={uncertain ? "Retry same request" : "Start Good Moral request"} pendingLabel="Starting request…"
        pending={creation.isPending} error={error} onConfirm={() => void send()}
        onCloseAutoFocus={(event) => { if (!createdId) { event.preventDefault(); reviewButton.current?.focus(); } }}
        completed={createdId ? { title: "Good Moral request started", children: "The request was created under the Student’s account. Their COMPASS notification and email delivery have been queued.", doneLabel: "Open request" } : null}
      >
        <p className="font-semibold text-ink">{student?.display_name}{student?.institutional_id ? ` · ${student.institutional_id}` : ""}</p>
        {student?.college ? <p>{student.college.name}</p> : null}
        <p>{student ? goodMoralVariantLabel(variant) : ""} · {intent?.variant === "CURRENT_STUDENT" ? `${student?.f4_eligibility?.year_level ?? ""} · ${intent.payload.semester}` : intent ? `${intent.payload.degree}${intent.payload.major ? ` · ${intent.payload.major}` : ""} · ${formatGoodMoralDate(intent.payload.graduation_date)}` : ""}</p>
        <p>This request will be created under the Student’s account. The Student will receive a COMPASS notification and email.</p>
      </ConsequentialActionDialog>
    </section>
  );
}
