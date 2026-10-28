"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { stepUpRequirement, type StepUpRequirement } from "@/features/account/security/step-up";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";
import { canManageOrganizationCatalog } from "@/features/institution-configuration/institution-access";
import { TableSkeleton } from "@/features/organization/components/organization-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getAuthGetSessionQueryOptions } from "@/lib/api/generated/auth/auth";
import { catalogErrorCode, catalogErrorMessage, uncertainCatalogOutcome } from "./catalog-errors";
import { CatalogImpact } from "./catalog-impact";
import { academicProgramLabel, draftError, initialDraft, makeCommand, parentLabel, type CatalogCommand, type CatalogIntent, type CatalogTarget } from "./catalog-model";
import { CatalogPolicyFields } from "./catalog-policy-fields";
import { catalogDetailKey, catalogImpactKey, executeCatalogCommand, readCatalogImpact, readCatalogTarget, reconcileCatalogCommand, refreshCatalog } from "./catalog-query";
import { CatalogReview } from "./catalog-review";

export function CatalogEditor({ intent, knownIds, canManageRelationships, onClose, onSaved }: {
  intent: CatalogIntent; knownIds: readonly string[]; canManageRelationships: boolean;
  onClose: () => void; onSaved: (target: CatalogTarget) => void;
}) {
  const { user, session } = usePortalSession();
  const owner = `${user.id}:${session.id}`;
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(() => initialDraft(intent));
  // This is the record the person chose to edit, not the latest query result.
  // A refetch must never silently rebase an unsent rename onto a new version.
  const [reviewedRename, setReviewedRename] = useState<CatalogTarget | null>(() => intent.mode === "rename" ? intent.target : null);
  const [review, setReview] = useState<CatalogCommand | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codeError, setCodeError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState<StepUpRequirement | null>(null);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<CatalogTarget | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [unconfirmed, setUnconfirmed] = useState<CatalogCommand | null>(null);
  const [denied, setDenied] = useState(false);
  const heading = useRef<HTMLSpanElement>(null);
  const reviewButton = useRef<HTMLButtonElement>(null);
  const running = useRef(false);
  const idsBeforeAttempt = useRef(knownIds);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; heading.current?.focus(); return () => { mounted.current = false; }; }, []);
  const context = intent.mode === "create" ? intent.parent : intent.target;
  const kind = intent.mode === "create" ? intent.kind : intent.target.kind;
  const target = useQuery({
    // The suffix distinguishes this selected presentation from Orval's raw transport response.
    queryKey: [...catalogDetailKey(context?.kind ?? kind, context?.record.id ?? ""), "catalog-review"],
    queryFn: ({ signal }) => context ? readCatalogTarget(context.kind, context.record.id, signal) : Promise.reject(new Error("No parent")),
    enabled: Boolean(context) && !denied,
    retry: false, staleTime: 0,
  });
  const retiring = intent.mode === "status" && draft.active === "inactive";
  const impact = useQuery({
    queryKey: [...catalogImpactKey(kind, context?.record.id ?? ""), "catalog-review"],
    queryFn: ({ signal }) => readCatalogImpact(kind, context?.record.id ?? "", signal),
    enabled: retiring && !denied, retry: false, staleTime: 0,
  });
  const confirmedTarget = safeQueryData(target);
  const current = intent.mode !== "create" ? confirmedTarget : undefined;
  const renameChanged = Boolean(reviewedRename && confirmedTarget && !sameRenameRecord(reviewedRename, confirmedTarget));
  const mutation = useMutation({ mutationFn: executeCatalogCommand, retry: false });
  const busy = reading || saving;
  const dirty = !saved && JSON.stringify(draft) !== JSON.stringify(initialDraft(intent));
  useUnsavedChangesGuard({ dirty, message: "Discard the unsaved Catalog change?" });
  const { confirmDiscard } = useUnsavedNavigation();
  const title = intent.mode === "create" ? `Add ${kind}` : intent.mode === "rename" ? `Rename ${kind}` : intent.mode === "policy" ? "Edit Program settings" : `${draft.active === "active" ? "Activate" : "Deactivate"} ${kind}`;

  function close() { if (!busy && (!dirty || confirmDiscard())) onClose(); }
  async function authority() {
    const latest = await queryClient.fetchQuery(getAuthGetSessionQueryOptions({ query: { retry: false, staleTime: 0 } }));
    const data = latest.data;
    if (!data.authenticated || `${data.user.id}:${data.session.id}` !== owner || !canManageOrganizationCatalog(data.user)) {
      setDenied(true);
      setReview(null);
      throw new Error("Catalog authority changed");
    }
  }
  async function reload() {
    if (context) await target.refetch({ throwOnError: true });
    if (retiring) await impact.refetch({ throwOnError: true });
  }
  async function prepare(event: FormEvent) {
    event.preventDefault();
    if (busy || running.current || saved || denied || unconfirmed) return;
    running.current = true;
    setError(null); setCodeError(null); setNotice(null);
    try {
      if (intent.mode === "rename" && renameChanged) {
        setNotice("This record changed. Compare the latest saved information and your draft, then choose Review latest record."); return;
      }
      const invalid = draftError(intent, draft, current);
      if (invalid) { setError(invalid); return; }
      setReading(true);
      await authority();
      const fresh = context ? (await target.refetch({ throwOnError: true })).data : undefined;
      const preview = retiring ? (await impact.refetch({ throwOnError: true })).data : undefined;
      if (!mounted.current) return;
      if (context && !fresh) throw new Error("Missing current target");
      if (intent.mode === "rename" && (!reviewedRename || !fresh || !sameRenameRecord(reviewedRename, fresh))) {
        setNotice("This record changed. Compare the latest saved information and your draft, then choose Review latest record."); return;
      }
      if (intent.mode !== "rename" && fresh && target.data && fresh.record.resource_version !== target.data.record.resource_version) {
        setNotice("This information was updated. Your input is preserved. Compare the latest saved values below, then review again."); return;
      }
      if (retiring && (!preview?.can_deactivate || preview.resource_version !== fresh?.record.resource_version)) {
        setError("Deactivation is unavailable. Review the latest impact and resolve its blockers."); return;
      }
      const invalidFresh = draftError(intent, draft, intent.mode === "create" ? undefined : fresh);
      if (invalidFresh) { setError(invalidFresh); return; }
      const command = makeCommand(intent, draft, intent.mode === "rename" ? reviewedRename ?? undefined : fresh);
      if (intent.mode === "rename") await execute(command);
      else setReview(command);
    } catch (caught) { if (mounted.current) setError(catalogErrorMessage(caught)); }
    finally { running.current = false; if (mounted.current) setReading(false); }
  }
  async function finishSave(result: CatalogTarget) {
    if (!mounted.current) return;
    setSaved(result); setUnconfirmed(null); setReview(null); setError(null);
    try {
      await refreshCatalog(queryClient, result);
      if (mounted.current) { setRefreshFailed(false); onSaved(result); }
    } catch {
      if (mounted.current) setRefreshFailed(true);
    }
  }
  async function reconcile(command: CatalogCommand) {
    setReading(true);
    try {
      await authority();
      const confirmed = await reconcileCatalogCommand(command, user.id, idsBeforeAttempt.current);
      if (!mounted.current) return;
      if (confirmed) { await finishSave(confirmed); return; }
      await reload();
      setError("We couldn't confirm whether this change was saved. Check its status before making another change.");
    } catch { if (mounted.current) setError("We couldn't confirm whether this change was saved. Check its status before making another change."); }
    finally { if (mounted.current) setReading(false); }
  }
  async function submit() {
    if (!review || running.current || busy || denied || saved || unconfirmed) return;
    running.current = true;
    try { await execute(review); }
    finally { running.current = false; }
  }
  async function execute(command: CatalogCommand) {
    setSaving(true);
    setError(null);
    try {
      await authority();
      if (!mounted.current) return;
      const result = await mutation.mutateAsync(command);
      await finishSave(result);
    } catch (caught) {
      if (!mounted.current) return;
      setReview(null);
      const requirement = stepUpRequirement(caught);
      if (requirement) {
        setStepUp(requirement);
        setNotice(catalogErrorMessage(caught));
      } else if (uncertainCatalogOutcome(caught) && !denied && !(caught instanceof Error && caught.message === "Catalog authority changed")) {
        setUnconfirmed(command);
        setNotice("Checking whether your change was saved.");
        await reconcile(command);
      } else {
        setError(catalogErrorMessage(caught));
        const code = catalogErrorCode(caught);
        if (code === "catalog_duplicate_code") setCodeError(catalogErrorMessage(caught));
        if (code === "permission_denied" || code === "invalid_session") { setDenied(true); void queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryOptions().queryKey }); }
        else { try { await reload(); } catch { setError(`${catalogErrorMessage(caught)} The latest details could not be loaded. Refresh before reviewing again.`); } }
      }
    } finally { if (mounted.current) setSaving(false); }
  }
  async function afterVerification() {
    setReading(true);
    try { await authority(); await reload(); setNotice(intent.mode === "rename" ? "Authenticator verified. Check the saved information and select Save changes when ready." : "Authenticator verified. Review the latest saved values and your proposed change, then confirm again."); }
    catch { setError("Verification succeeded, but the latest details could not be loaded. Refresh before reviewing again."); }
    finally { setReading(false); }
    // No retained command and no mutation call after MFA.
  }
  return <Panel className="mb-5" aria-labelledby="catalog-editor-heading">
    <PanelHeader title={<span ref={heading} tabIndex={-1} className="outline-none" id="catalog-editor-heading">{title}</span>} description={intent.mode === "create" ? undefined : intent.mode === "rename" ? "Edit the selected record below." : "Review the current record before changing it."} />
    <PanelBody>
      {saved ? <Notice tone={refreshFailed ? "warning" : "success"} role="status" action={<>
        {refreshFailed ? <Button variant="secondary" disabled={busy} onClick={() => { setReading(true); void finishSave(saved).finally(() => setReading(false)); }}>Retry refresh</Button> : null}
        <Button variant="secondary" disabled={busy} onClick={onClose}>Done</Button>
      </>}>{refreshFailed ? "The change was saved, but the latest details could not be loaded." : "Changes saved."}</Notice> : <>
        {notice ? <Notice className="mb-4" role="status">{notice}</Notice> : null}
        {error ? <Notice className="mb-4" tone="danger" role="alert">{error}</Notice> : null}
        {denied ? <Notice tone="warning" action={<Button variant="secondary" onClick={onClose}>Close editor</Button>}>Catalog management access or your sign-in changed. This editor is unavailable.</Notice> : <>
          {context && target.isPending ? <TableSkeleton label="Loading current Catalog record…" /> : context && target.isError ? <Notice tone="warning" action={<Button variant="secondary" disabled={busy} onClick={() => void target.refetch()}>Refresh record</Button>}>The latest record could not be loaded. Your input is retained; review is unavailable until refresh succeeds.</Notice> : null}
          {confirmedTarget ? <div className="mb-5 space-y-1 break-words text-sm" aria-label="Latest saved record">
            <h3 className="font-semibold">{intent.mode === "create" ? "Fixed parent" : target.isError ? "Last confirmed record" : "Latest saved record"}</h3>
            <p>{confirmedTarget.record.name} · <span className="font-mono">{confirmedTarget.record.code}</span></p>
            <p>{parentLabel(confirmedTarget)} · {confirmedTarget.record.is_active ? "Active" : "Inactive"}</p>
            {confirmedTarget.kind === "program" ? <p>{academicProgramLabel(confirmedTarget.record)}</p> : null}
          </div> : null}
          {renameChanged && reviewedRename && !target.isError ? <Notice className="mb-4" tone="warning" action={<Button variant="secondary" disabled={busy || target.isFetching} onClick={() => { if (confirmedTarget) { setReviewedRename(confirmedTarget); setNotice(null); setError(null); } }}>Review latest record</Button>}>
            This record changed since you opened it. Previously reviewed name: {reviewedRename.record.name}. Compare the latest saved record above with your draft before continuing.
          </Notice> : null}
          <form onSubmit={(event) => void prepare(event)} className="space-y-5" aria-label={title}>
            <fieldset disabled={busy || Boolean(unconfirmed)} className="space-y-5">
              {intent.mode === "create" ? <div className="grid gap-2">
                <Label htmlFor="catalog-code">{kind === "campus" ? "Campus" : kind === "college" ? "College" : "Program"} code</Label>
                <Input id="catalog-code" required maxLength={32} value={draft.code} aria-invalid={Boolean(codeError)} aria-describedby={codeError ? "catalog-code-help catalog-code-error" : "catalog-code-help"} onChange={(event) => { setCodeError(null); setDraft({ ...draft, code: event.target.value }); }} />
                {codeError ? <p id="catalog-code-error" className="text-sm text-danger">{codeError}</p> : null}
                <p id="catalog-code-help" className="text-sm text-muted">Use the official identifier. Code and parent cannot be changed through ordinary editing after creation.</p>
              </div> : null}
              {intent.mode === "create" || intent.mode === "rename" ? <div className="grid gap-2">
                <Label htmlFor="catalog-name">{intent.mode === "rename" ? "New official name" : "Official name"}</Label>
                <Input id="catalog-name" required maxLength={160} value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
              </div> : null}
              {intent.mode === "create" ? <div className="grid gap-2"><Label htmlFor="catalog-active">Initial status</Label><Select id="catalog-active" required value={draft.active} onChange={(event) => { const value = event.target.value; if (value === "active" || value === "inactive") setDraft({ ...draft, active: value }); }}>
                <option value="" disabled>Choose status</option><option value="active">Active</option><option value="inactive">Inactive</option>
              </Select></div> : null}
              {intent.mode === "policy" || (intent.mode === "create" && kind === "program") ? <CatalogPolicyFields draft={draft} onChange={setDraft} disabled={busy} /> : null}
              {intent.mode === "rename" ? <p className="text-sm text-muted">The new official name may appear in current linked views. Finalized historical records keep their saved facts; documents are not regenerated.</p> : null}
              {intent.mode === "status" && draft.active === "active" ? <p className="text-sm text-muted">Parent records must be active. Programs need a classification and year levels. Descendants are not activated automatically, and historical assignments are not restored automatically.</p> : null}
              <div className="grid gap-2"><Label htmlFor="catalog-basis">Change note</Label><Input id="catalog-basis" required maxLength={160} placeholder={intent.mode === "rename" ? `Corrected the ${kind} name.` : intent.mode === "status" ? `${draft.active === "active" ? "Activated" : "Deactivated"} the ${kind}.` : intent.mode === "policy" ? "Updated Program settings." : `Added a ${kind}.`} value={draft.basis} aria-describedby="catalog-basis-help" onChange={(event) => setDraft({ ...draft, basis: event.target.value })} /><p id="catalog-basis-help" className="text-sm text-muted">A short note about this change, up to 160 characters. It will appear in the change history.</p></div>
            </fieldset>
            {retiring ? impact.isPending ? <TableSkeleton label="Loading deactivation impact…" /> : impact.isError ? <Notice tone="warning" action={<Button variant="secondary" onClick={() => void impact.refetch()}>Refresh impact</Button>}>The current impact could not be confirmed. Deactivation is unavailable.</Notice> : impact.data ? <><CatalogImpact impact={impact.data} canManageRelationships={canManageRelationships} /><Button variant="secondary" disabled={busy} onClick={() => { setReview(null); void impact.refetch(); }}>Refresh impact</Button></> : null : null}
            {unconfirmed ? <Notice tone="warning" action={<Button variant="secondary" disabled={busy} onClick={() => void reconcile(unconfirmed)}>Check saved state</Button>}>The save is still unconfirmed. Check saved state before making another change.</Notice> : null}
            <div className="flex flex-wrap justify-end gap-2"><Button variant="secondary" disabled={busy} onClick={close}>Cancel</Button><Button ref={reviewButton} type="submit" disabled={busy || renameChanged || Boolean(unconfirmed) || (Boolean(context) && (!target.data || target.isError || target.isFetching)) || (retiring && (!impact.data?.can_deactivate || impact.isError || impact.isFetching))}>{saving ? "Saving…" : reading ? "Loading latest details…" : intent.mode === "rename" ? "Save changes" : "Review change"}</Button></div>
          </form>
        </>}
      </>}
    </PanelBody>
    <ConsequentialActionDialog open={Boolean(review)} title={`Review: ${title}`} confirmLabel={title === "Edit Program settings" ? "Save Program settings" : title} pendingLabel="Saving Catalog change…" pending={saving} confirmDisabled={reading || denied} variant={retiring ? "danger" : "primary"} error={null} onOpenChange={(open) => { if (!open) setReview(null); }} onConfirm={() => void submit()} onCloseAutoFocus={(event) => { event.preventDefault(); reviewButton.current?.focus(); }}>
      {review ? <CatalogReview command={review} parent={intent.mode === "create" ? target.data : undefined} impact={retiring ? impact.data : undefined} /> : null}
    </ConsequentialActionDialog>
    <StepUpDialog setupInNewTab reviewAfterVerification open={Boolean(stepUp)} requirement={stepUp ?? "verify"} onOpenChange={(open) => { if (!open) setStepUp(null); }} onVerified={afterVerification} />
  </Panel>;
}

function sameRenameRecord(reviewed: CatalogTarget, latest: CatalogTarget) {
  return reviewed.kind === latest.kind && reviewed.record.id === latest.record.id
    && reviewed.record.resource_version === latest.record.resource_version
    && reviewed.record.name === latest.record.name && reviewed.record.code === latest.record.code
    && reviewed.record.is_active === latest.record.is_active && parentLabel(reviewed) === parentLabel(latest)
    && (reviewed.kind === "campus" || (reviewed.kind === "college" && latest.kind === "college" && reviewed.record.campus.id === latest.record.campus.id)
      || (reviewed.kind === "program" && latest.kind === "program" && reviewed.record.college.id === latest.record.college.id && reviewed.record.college.campus.id === latest.record.college.campus.id));
}
