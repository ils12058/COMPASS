"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { ManagedActionFeedback, useInvalidateManagedAccount, useManagedAction } from "@/features/accounts/components/account-action";
import { FacultyCollegeField } from "@/features/accounts/components/faculty-college-field";
import { useManagedAccount } from "@/features/accounts/detail/account-detail-frame";
import { useAccountsFacultyCollegeChoices, useAccountsSetFacultyAffiliation } from "@/lib/api/generated/accounts/accounts";
import type { FacultyAffiliationUpdateRequest } from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/errors";

export function ManagedFacultyAffiliation() {
  const account = useManagedAccount();
  const affiliation = account.faculty_affiliation;
  const [college, setCollege] = useState(affiliation?.college_id ?? "");
  const [draftVersion, setDraftVersion] = useState(affiliation?.resource_version ?? 0);
  const stale = draftVersion !== (affiliation?.resource_version ?? 0);
  const choices = useAccountsFacultyCollegeChoices({ query: { retry: false } });
  const selected = choices.data?.data.find((item) => item.id === college);
  const [basis, setBasis] = useState("");
  const [review, setReview] = useState<FacultyAffiliationUpdateRequest | null>(null);
  const action = useManagedAction();
  const invalidate = useInvalidateManagedAccount(account.id);
  const save = useAccountsSetFacultyAffiliation();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    action.setError(null);
    setReview({ college_id: college || null, basis: basis.trim(), expected_resource_version: draftVersion });
  }
  async function confirm() {
    if (!review) return;
    const response = await action.run(
      () => save.mutateAsync({ userId: account.id, data: review }),
      "The affiliation could not be saved. Check the current College selection and try again.",
      () => setReview(null),
      (error) => {
        if (error instanceof CompassApiError && error.status === 409) {
          setReview(null);
          action.setError("The affiliation changed. The latest assignment is loading; review it before saving again.");
          void invalidate();
        }
      },
    );
    if (!response) return;
    setReview(null);
    setBasis("");
    setDraftVersion(response.data.faculty_affiliation?.resource_version ?? 0);
    setCollege(response.data.faculty_affiliation?.college_id ?? "");
    await invalidate();
    action.setNotice("Faculty affiliation saved.");
  }
  return (
    <Panel aria-labelledby="faculty-affiliation-heading">
      <PanelHeader title="Faculty affiliation" titleId="faculty-affiliation-heading" />
      <PanelBody>
        <p className="mb-4 text-sm text-ink">Current home College: {affiliation?.college_name ? `${affiliation.campus_name} · ${affiliation.college_name}${affiliation.active ? "" : " (inactive)"}` : "Not assigned"}</p>
        {stale ? <p role="status" className="mb-4 text-sm">The assignment changed. <Button variant="secondary" onClick={() => { setCollege(affiliation?.college_id ?? ""); setDraftVersion(affiliation?.resource_version ?? 0); action.setError(null); }}>Review latest assignment</Button></p> : null}
        <form className="grid max-w-lg gap-4" onSubmit={submit}>
          <FacultyCollegeField id="faculty-home-college" value={college} onChange={setCollege} disabled={save.isPending} />
          <div className="grid gap-2">
            <Label htmlFor="faculty-assignment-basis">Institutional assignment basis</Label>
            <Input id="faculty-assignment-basis" required maxLength={500} value={basis} onChange={(event) => setBasis(event.target.value)} disabled={save.isPending} />
          </div>
          <Button type="submit" disabled={stale || save.isPending || !basis.trim() || college === (affiliation?.college_id ?? "")}>Review affiliation</Button>
        </form>
        <ManagedActionFeedback action={action} showMessages={!review} />
      </PanelBody>
      <ConsequentialActionDialog open={review !== null} title="Change Faculty home College?"
        confirmLabel="Save affiliation" pendingLabel="Saving affiliation…" pending={save.isPending}
        error={action.error} onOpenChange={(open) => { if (!open) setReview(null); }} onConfirm={() => void confirm()}>
        <p>This records an institutional home College for {account.full_name}. It does not grant access to Student records or enable digital Referrals.</p>
        <p className="mt-3 text-sm">Home College: {selected ? `${selected.campus_name} · ${selected.name}` : review?.college_id ? "Selected College is no longer available" : "Not assigned"}</p>
        <p className="mt-3 break-words text-sm">Assignment basis: {review?.basis}</p>
      </ConsequentialActionDialog>
    </Panel>
  );
}
