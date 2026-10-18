"use client";
import { invalidateFollowups } from "./followups-data";
import { useFollowupsFreshness, followupQueryFreshness } from "./followups-data";
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FollowupsHelp } from "./followups-help";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useGuidanceFollowupsRecoverable, useGuidanceFollowupsEligibleAssignees, guidanceFollowupsReassign } from "@/lib/api/generated/guidance-followups/guidance-followups";
import type { FollowUpSummary } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { followupAccess, FollowupRestricted, FollowupFailure, followupError } from "./followups-shared";
export function FollowupsReassignment() {
  const { user } = usePortalSession(); const access = followupAccess(user);
  useFollowupsFreshness(access.view);
  const [page, setPage] = useState(1); const [selected, setSelected] = useState<FollowUpSummary | null>(null);
  const query = useGuidanceFollowupsRecoverable({ page }, { query: { ...followupQueryFreshness, enabled: access.manage, retry: false } });
  if (!access.manage) return <FollowupRestricted />;
  return <><PageHeader help={<FollowupsHelp />} title="Recover assignments" description="Restore responsibility for operational follow-ups whose original staff member no longer meets eligibility. Counselor-confidential follow-ups are excluded." back={<Link href="/portal/follow-ups" className={pageBackLinkClass}>Back to Follow-Ups</Link>} />
    <Panel><PanelHeader title="Assignments needing recovery" />{query.isPending ? <p role="status" className="p-5">Checking assignments…</p> : query.isError ? <FollowupFailure error={query.error} retry={() => void query.refetch()} /> : <>
      {query.data?.data.items.length ? <ul className="divide-y divide-border px-5">{query.data.data.items.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-4 py-3"><div><p className="flex items-center gap-2 font-semibold"><PersonAvatar displayName={row.student_name} photoUrl={row.student_profile_photo_url} photoUpdatedAt={row.student_profile_photo_updated_at} size="compact" />{row.student_name}</p><p className="mt-1 flex items-center gap-2 text-sm"><PersonAvatar displayName={row.assigned_to_name} photoUrl={row.assigned_to_profile_photo_url} photoUpdatedAt={row.assigned_to_profile_photo_updated_at} size="compact" />{row.assigned_to_name} · Due {formatInstitutionalDateTime(row.due_at)}</p></div><Button variant="secondary" onClick={() => setSelected(row)}>Recover assignment <span className="sr-only">for {row.student_name}</span></Button></li>)}</ul> : <PanelMessage>No operational follow-ups need recovery in your current scope.</PanelMessage>}
      {query.data ? <div className="px-5"><CanonicalPagination page={query.data.data.page} hasNext={query.data.data.has_next && page < 100} onPageChange={setPage} /></div> : null}
    </>}</Panel>{selected ? <Reassignment item={selected} onClose={() => { setSelected(null); void query.refetch(); }} /> : null}
  </>;
}
function Reassignment({ item, onClose }: { item: FollowUpSummary; onClose: () => void }) {
  const client = useQueryClient(); const [staff, setStaff] = useState(""); const [page, setPage] = useState(1);
  const [key, setKey] = useState(() => crypto.randomUUID()); const [error, setError] = useState<string | null>(null);
  const continuation = useStepUpContinuation();
  const options = useGuidanceFollowupsEligibleAssignees({ student_id: item.student_id, category: item.category, page }, { query: { retry: false } });
  const mutation = useMutation({ mutationFn: () => guidanceFollowupsReassign(item.id, { assigned_to_id: staff, expected_version: item.version }, { headers: { "Idempotency-Key": key } }) });
  async function save() {
    setError(null);
    const result = await continuation.run(() => mutation.mutateAsync(), {
      onFailure: (caught) => setError(followupError(caught)),
    });
    if (!result) return;
    await invalidateFollowups(client);
    onClose();
  }
  return <><ConsequentialActionDialog open title={`Recover assignment for ${item.student_name}?`} confirmLabel="Recover assignment" pendingLabel="Recovering assignment…" pending={mutation.isPending} confirmDisabled={!staff || options.isFetching || options.isError} error={error} onOpenChange={open => { if (!open) onClose(); }} onConfirm={() => void save()} choices={<>
    <Label htmlFor="recovery-assignee">Responsible staff member</Label><Select id="recovery-assignee" value={staff} disabled={mutation.isPending} onChange={event => { setStaff(event.target.value); setKey(crypto.randomUUID()); }}><option value="">Choose a staff member</option>{options.data?.data.items.map(row => <option key={row.id} value={row.id}>{row.display_name}</option>)}</Select>
    {options.isError ? <FollowupFailure error={options.error} retry={() => void options.refetch()} /> : null}
    {options.data ? <CanonicalPagination page={options.data.data.page} hasNext={options.data.data.has_next} onPageChange={page => { setPage(page); setStaff(""); }} /> : null}
  </>}><p>Responsibility transfers to the selected authorized staff member. Protected descriptions and source records are not shown during recovery.</p>{continuation.notice ? <p role="status" className="mt-2 text-sm text-muted">{continuation.notice}</p> : null}</ConsequentialActionDialog><StepUpDialog open={continuation.open} requirement={continuation.requirement} onOpenChange={(open) => { continuation.setOpen(open); if (!open) setError(null); }} isContinuing={continuation.isContinuing} onVerified={continuation.continueAfterVerification} /></>;
}
