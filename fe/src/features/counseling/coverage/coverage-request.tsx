"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { institutionalDateTimeInputToISO } from "@/lib/institutional-time";
import type { CoverageConfiguration, ContinuityReason, ContinuityRequestInput } from "@/lib/api/generated/model";
import * as api from "@/lib/api/generated/counseling/counseling";
import { CoverageError, reasonLabels, referenceClass } from "./coverage-shared";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
export function CoverageRequest({ configuration, initialStudent, initialOriginal, onCreated }: {
    configuration: CoverageConfiguration;
    initialStudent: string;
    initialOriginal: string;
    onCreated: () => void;
}) {
    const { user } = usePortalSession();
    const router = useRouter();
    const [caseIndex, setCaseIndex] = useState("");
    const [receiver, setReceiver] = useState("");
    const [reason, setReason] = useState<ContinuityReason>(configuration.reason_categories[0]);
    const [start, setStart] = useState("");
    const [end, setEnd] = useState("");
    const [ids, setIds] = useState<string[]>([]);
    const [page, setPage] = useState(1);
    const [review, setReview] = useState(false);
    const [notice, setNotice] = useState("");
    const [intent] = useState(() => crypto.randomUUID());
    const picked = configuration.office_cases[Number(caseIndex)];
    const student = initialStudent || (caseIndex !== "" ? picked?.student_id : "");
    const original = initialStudent ? initialOriginal : (caseIndex !== "" ? picked?.original_counselor_id : "");
    const options = api.useCounselingCoverageSelectSources({ student_id: student ?? "", original_counselor_id: original ?? "", page }, { query: { enabled: Boolean(student && original), retry: false, gcTime: 0, queryKey: [...api.getCounselingCoverageSelectSourcesQueryKey({ student_id: student ?? "", original_counselor_id: original ?? "", page }), user.id] } });
    const save = useMutation({ mutationFn: (data: ContinuityRequestInput) => api.counselingContinuityRequestCoverage(data), retry: false, gcTime: 0 });
    const rows = options.data?.data.items ?? [];
    // Changing a selection page deliberately clears checked records: only visible exact references submit.
    const startsAt = institutionalDateTimeInputToISO(start), expiresAt = institutionalDateTimeInputToISO(end);
    const duration = startsAt && expiresAt ? Date.parse(expiresAt) - Date.parse(startsAt) : 0;
    const valid = Boolean(student && original && receiver && ids.length && ids.length <= 32 && duration > 0 && duration <= configuration.maximum_duration_seconds * 1000 && options.isSuccess && !options.isFetching);
    useUnsavedChangesGuard({ dirty: Boolean(start || end || receiver || ids.length) && !save.isSuccess, message: "Leave this unsaved coverage request?" });
    async function submit() {
        if (!valid || !startsAt || !expiresAt || !student || !original)
            return;
        try {
            const result = await save.mutateAsync({ student_id: student, original_counselor_id: original, receiving_counselor_id: receiver, coverage_kind: original === user.id ? "PLANNED_HANDOFF" : "TEMPORARY_COVERAGE", reason_category: reason, starts_at: startsAt, expires_at: expiresAt, request_id: intent, expected_version: 0, scopes: rows.filter(r => ids.includes(r.source_id)).map(({ resource_kind, source_id, projection }) => ({ resource_kind, source_id, projection })) });
            setReview(false);
            onCreated();
            router.push(`/portal/counseling/coverage/${result.data.id}`);
        }
        catch {
            setReview(false);
            setIds([]);
            setNotice("The request was not confirmed. Review the latest record selection before submitting again.");
            void options.refetch();
        }
    }
    return <Panel className="mb-5"><PanelHeader title="Request coverage" description="Choose one recipient, an explicit period and exact records."/><form className="space-y-5 p-4 sm:p-5" onSubmit={e => { e.preventDefault(); if (valid)
        setReview(true); }}>
  {!initialStudent ? <div><Label htmlFor="coverage-case">Authorized case</Label><Select id="coverage-case" value={caseIndex} onChange={e => { setCaseIndex(e.target.value); setIds([]); setReceiver(""); setPage(1); }}><option value="">Select an authorized case</option>{configuration.office_cases.map((c, i) => <option key={`${c.student_id}-${c.original_counselor_id}`} value={i}>Student {c.student_id} · Original Counselor {c.original_counselor_id}</option>)}</Select>{!configuration.office_cases.length ? <p className="mt-2 text-sm text-muted">Open Request coverage from an existing Counseling Encounter. An approved office procedure is required for unexpected absence.</p> : null}</div> : <p className={referenceClass}>Student {student} · Original Counselor {original}</p>}
  {student && original ? <>{options.isPending ? <p role="status">Checking eligible records…</p> : options.isError ? <CoverageError error={options.error} retry={() => void options.refetch()}/> : <>
   <div><Label htmlFor="coverage-receiver">Receiving Counselor</Label><Select id="coverage-receiver" required value={receiver} onChange={e => setReceiver(e.target.value)}><option value="">Select a Counselor</option>{options.data.data.receivers.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</Select></div>
   <fieldset className="space-y-3"><legend className="mb-2 font-semibold">Selected records</legend><p className="text-sm text-muted">Select up to 32 exact records.</p>{rows.length ? rows.map(r => <label key={r.source_id} className="flex min-h-11 items-start gap-3"><input className="mt-1" type="checkbox" disabled={!ids.includes(r.source_id) && ids.length >= 32} checked={ids.includes(r.source_id)} onChange={e => setIds(e.target.checked ? [...ids, r.source_id] : ids.filter(id => id !== r.source_id))}/><span className="min-w-0 text-sm">{r.resource_kind === "ENCOUNTER" ? "Encounter metadata" : "Finalized Counselor Evaluation"} · {formatCounselingDateTime(r.recorded_at)}<span className={`block ${referenceClass}`}>{r.source_id}</span></span></label>) : <PanelMessage>No eligible source records.</PanelMessage>}</fieldset>
   <div className="flex items-center gap-3"><Button type="button" variant="secondary" disabled={page === 1} onClick={() => { setPage(page - 1); setIds([]); }}>Previous records</Button><Button type="button" variant="secondary" disabled={!options.data.data.has_next} onClick={() => { setPage(page + 1); setIds([]); }}>Next records</Button></div>
  </>}
  <div><Label htmlFor="coverage-reason">Coverage purpose</Label><Select id="coverage-reason" value={reason} onChange={e => setReason(e.target.value as ContinuityReason)}>{configuration.reason_categories.map(r => <option key={r} value={r}>{reasonLabels[r]}</option>)}</Select></div>
  <div className="grid gap-4 sm:grid-cols-2"><div><Label htmlFor="coverage-start">Starts (Philippine time)</Label><Input id="coverage-start" required type="datetime-local" value={start} onChange={e => setStart(e.target.value)}/></div><div><Label htmlFor="coverage-end">Expires (Philippine time)</Label><Input id="coverage-end" required type="datetime-local" value={end} onChange={e => setEnd(e.target.value)}/></div></div>
  {end && !valid ? <p role="status" className="text-sm text-muted">Select a recipient and at least one record. Expiry must follow the start, within the approved maximum of {configuration.maximum_duration_seconds / 3600} hours.</p> : null}
  {notice ? <p role="alert">{notice}</p> : null}{save.error ? <CoverageError error={save.error}/> : null}<Button type="submit" disabled={!valid || save.isPending}>Review request</Button></> : null}
 </form><ConsequentialActionDialog open={review} onOpenChange={setReview} title="Request case coverage?" confirmLabel="Submit request" pendingLabel="Submitting…" pending={save.isPending} error={null} onConfirm={() => void submit()}><span className="block">Receiving Counselor: {options.data?.data.receivers.find(r => r.id === receiver)?.name}.</span><span className="block">Purpose: {reasonLabels[reason]}. Starts {startsAt ? formatCounselingDateTime(startsAt) : ""}.</span><span className="block">{ids.length} selected records, until {expiresAt ? formatCounselingDateTime(expiresAt) : ""}. Independent approval is required before access begins.</span><ul className="mt-3 space-y-2">{rows.filter(r => ids.includes(r.source_id)).map(r => <li key={r.source_id} className="break-all text-xs">{r.resource_kind === "ENCOUNTER" ? "Encounter metadata" : "Finalized Evaluation"}: {r.source_id}</li>)}</ul></ConsequentialActionDialog></Panel>;
}
