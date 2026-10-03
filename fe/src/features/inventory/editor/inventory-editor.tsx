"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Select } from "@/components/ui/select";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { BackgroundSection } from "@/features/inventory/editor/background-section";
import { EducationSection } from "@/features/inventory/editor/education-section";
import { FamilySection } from "@/features/inventory/editor/family-section";
import { HealthSection } from "@/features/inventory/editor/health-section";
import { InterestsSection } from "@/features/inventory/editor/interests-section";
import { OrganizationsSection } from "@/features/inventory/editor/organizations-section";
import { PersonalSection } from "@/features/inventory/editor/personal-section";
import { PlansSection } from "@/features/inventory/editor/plans-section";
import { ReviewSection } from "@/features/inventory/editor/review-section";
import { getInventorySubmissionIssues, normalizeInventoryPayload, toInventoryPayload, type InventorySubmissionIssue } from "@/features/inventory/inventory-payload";
import { inventorySections, type InventorySectionId } from "@/features/inventory/inventory-presentation";
import { formatInventoryDate, InventoryHeading, InventoryNotice, inventoryErrorMessage } from "@/features/inventory/inventory-shared";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import type { InventoryPayload, InventoryResponse } from "@/lib/api/generated/model";
import {
  getInventoryGetMyCurrentQueryKey,
  getInventoryGetMyStatusQueryKey,
  getInventoryListMyHistoryQueryKey,
  useInventorySubmitMyCurrent,
  useInventoryUpdateMyCurrent,
} from "@/lib/api/generated/inventory/inventory";
import { useOrganizationListPrograms } from "@/lib/api/generated/organization/organization";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function InventoryEditor({ inventory }: { inventory: InventoryResponse }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const canDiscoverPrograms = user.capabilities.includes("organization.structure.view");
  const programQuery = useOrganizationListPrograms(
    { is_active: true },
    { query: { enabled: canDiscoverPrograms, retry: false } },
  );
  const activePrograms = programQuery.data?.data.items ?? [];
  const activeProgramIds = programQuery.data
    ? new Set(activePrograms.map((program) => program.id))
    : undefined;

  const [draft, setDraft] = useState(() => toInventoryPayload(inventory));
  const [saved, setSaved] = useState(() => toInventoryPayload(inventory));
  const [section, setSection] = useState<InventorySectionId>("personal");
  const [validationVisible, setValidationVisible] = useState(false);
  const pendingTargetRef = useRef<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [writeBlocked, setWriteBlocked] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  // Covers the whole submission, including the refresh after the request succeeds.
  const [submitting, setSubmitting] = useState(false);
  const save = useInventoryUpdateMyCurrent();
  const submit = useInventorySubmitMyCurrent();
  const submitPending = submit.isPending || submitting;
  const pending = save.isPending || submitPending;
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  useUnsavedChangesGuard({
    dirty,
    message: "Discard your unsaved Individual Inventory changes?",
  });
  const issues = getInventorySubmissionIssues(draft, activeProgramIds);
  const currentSectionIndex = inventorySections.findIndex((item) => item.id === section);
  const currentCorrection = inventory.correction_pending ? inventory.latest_correction : null;

  useEffect(() => {
    const pendingTargetId = pendingTargetRef.current;
    if (!pendingTargetId) return;
    pendingTargetRef.current = null;
    const target = document.getElementById(pendingTargetId);
    if (!target) return;
    target.scrollIntoView({ block: "center" });
    const focusTarget = target.matches("input, select, textarea, button")
      ? target
      : target.querySelector<HTMLElement>("input, select, textarea, button");
    (focusTarget as HTMLElement | null)?.focus({ preventScroll: true });
  }, [section]);

  function navigateToSection(next: InventorySectionId) {
    if (next === "review") setValidationVisible(true);
    setSection(next);
  }

  function selectIssue(issue: InventorySubmissionIssue) {
    setValidationVisible(true);
    pendingTargetRef.current = issue.targetId;
    setSection(issue.section);
  }

  function updateDraft(patch: Partial<InventoryPayload>) {
    setDraft((current) => ({ ...current, ...patch }));
    setSaveError(null);
    setSubmitError(null);
    setNotice(null);
  }

  function setMutationError(error: unknown, fallback: string) {
    const code = error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
    const message = inventoryErrorMessage(error, fallback);
    if (code === "current_student_required") {
      setWriteBlocked(true);
      void queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() });
    }
    if (code === "inventory_conflict") {
      void queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() });
      void queryClient.invalidateQueries({ queryKey: getInventoryGetMyCurrentQueryKey() });
      void queryClient.invalidateQueries({ queryKey: getInventoryListMyHistoryQueryKey() });
    }
    return message;
  }

  async function saveProgress(continueToNext = false): Promise<boolean> {
    if (pending) return false;
    if (!dirty) {
      if (continueToNext && currentSectionIndex < inventorySections.length - 1) {
        navigateToSection(inventorySections[currentSectionIndex + 1].id);
      }
      return true;
    }
    setSaveError(null);
    setNotice(null);
    try {
      const response = await save.mutateAsync({ data: normalizeInventoryPayload(draft) });
      const canonical = toInventoryPayload(response.data);
      setDraft(canonical);
      setSaved(canonical);
      queryClient.setQueryData(getInventoryGetMyCurrentQueryKey(), response);
      await queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() });
      setNotice("Progress saved.");
      if (continueToNext && currentSectionIndex < inventorySections.length - 1) {
        navigateToSection(inventorySections[currentSectionIndex + 1].id);
      }
      return true;
    } catch (error) {
      setSaveError(setMutationError(error, "Your Individual Inventory progress could not be saved."));
      return false;
    }
  }

  async function submitInventory() {
    if (pending || dirty || issues.length > 0) return;
    setSubmitError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      const response = await submit.mutateAsync();
      const canonical = toInventoryPayload(response.data);
      setDraft(canonical);
      setSaved(canonical);
      queryClient.setQueryData(getInventoryGetMyCurrentQueryKey(), response);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getInventoryListMyHistoryQueryKey() }),
      ]);
      setConfirmSubmit(false);
      router.replace("/portal/inventory/current");
    } catch (error) {
      setSubmitError(setMutationError(error, "Your Individual Inventory could not be submitted."));
    } finally {
      setSubmitting(false);
    }
  }

  if (writeBlocked) {
    return (
      <div className="space-y-6">
        <InventoryHeading title="Individual Inventory" />
        <InventoryNotice title="Editing is no longer available" tone="warning" role="alert">
          You can still read this record, but you can no longer edit or submit it because you are no longer a current student.
        </InventoryNotice>
        <GuardedPortalLink
          href="/portal/inventory"
          className={buttonVariants({ variant: "secondary" })}
        >
          Return to Individual Inventory
        </GuardedPortalLink>
      </div>
    );
  }

  const sectionProps = {
    draft,
    onChange: updateDraft,
    programSnapshot: inventory.program,
    activePrograms,
    programLookupPending: programQuery.isPending && canDiscoverPrograms,
    programLookupError: programQuery.isError,
    programDiscoveryAllowed: canDiscoverPrograms,
    validationIssues: validationVisible
      ? issues.filter((issue) => issue.section === section)
      : [],
  };

  return (
    <section aria-labelledby="inventory-editor-heading" aria-busy={pending}>
      <InventoryHeading
        title="Individual Inventory"
        description={`${inventory.academic_year.label} · ${inventory.form_revision.official_code} · Revision ${inventory.form_revision.official_revision}`}
      />

      <div className="mt-6">
        <InventoryNotice>
          Your Individual Inventory helps the Guidance and Counseling Office understand your needs and future plans. Please provide accurate information. Your responses are handled as confidential Student information.
        </InventoryNotice>
      </div>

      {currentCorrection ? (
        <div className="mt-5">
          <InventoryNotice title="Correction requested" tone="warning">
            <p className="whitespace-pre-wrap">{currentCorrection.message}</p>
            <p className="mt-2 text-xs text-muted">Requested {formatInventoryDate(currentCorrection.requested_at)}</p>
          </InventoryNotice>
        </div>
      ) : null}

      <div className="mt-8 md:grid md:grid-cols-[13rem_minmax(0,1fr)] md:gap-8">
        <div className="mb-6 md:mb-0">
          <label htmlFor="inventory-section-select" className="mb-2 block text-sm font-semibold text-ink md:sr-only">
            Inventory section
          </label>
          <Select
            id="inventory-section-select"
            className="min-h-11 font-semibold md:hidden"
            value={section}
            onChange={(event) => {
              const next = inventorySections.find((item) => item.id === event.target.value);
              if (next) navigateToSection(next.id);
            }}
          >
            {inventorySections.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}{item.id === "review" && issues.length ? ` · ${issues.length} needs attention` : ""}
              </option>
            ))}
          </Select>
          <nav aria-label="Individual Inventory sections" className="hidden border-y border-border md:block">
            <ol>
              {inventorySections.map((item, index) => {
                const count = issues.filter((issue) => issue.section === item.id).length;
                const active = section === item.id;
                return (
                  <li key={item.id} className="border-b border-border last:border-b-0">
                    <button
                      type="button"
                      aria-current={active ? "step" : undefined}
                      className={`flex min-h-12 w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${active ? "border-l-4 border-brand bg-brand-subtle font-semibold text-brand" : "text-ink hover:bg-surface-muted"}`}
                      onClick={() => navigateToSection(item.id)}
                    >
                      <span><span className="mr-2 text-xs text-muted">{index + 1}.</span>{item.label}</span>
                      {count ? <span className="shrink-0 text-xs font-semibold text-warning">{count}</span> : null}
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>
        </div>

        <div className="min-w-0">
          <div className="mb-5">
            <p className="text-xs font-semibold text-muted">
              Section {currentSectionIndex + 1} of {inventorySections.length}
            </p>
            <h2 id="inventory-editor-heading" className="mt-1 font-heading text-xl font-semibold text-ink">
              {inventorySections[currentSectionIndex]?.label}
            </h2>
          </div>

          {saveError ? <div className="mb-4"><InventoryNotice tone="danger" role="alert">{saveError}</InventoryNotice></div> : null}
          {submitError ? <div className="mb-4"><InventoryNotice tone="danger" role="alert">{submitError}</InventoryNotice></div> : null}
          {notice ? <div className="mb-4"><InventoryNotice tone="success">{notice}</InventoryNotice></div> : null}

          <fieldset disabled={pending} className="min-w-0 disabled:opacity-100">
            {section === "personal" ? <PersonalSection {...sectionProps} /> : null}
            {section === "family" ? <FamilySection {...sectionProps} /> : null}
            {section === "background" ? <BackgroundSection {...sectionProps} /> : null}
            {section === "health" ? <HealthSection {...sectionProps} /> : null}
            {section === "education" ? <EducationSection {...sectionProps} /> : null}
            {section === "interests" ? <InterestsSection {...sectionProps} /> : null}
            {section === "organizations" ? <OrganizationsSection {...sectionProps} /> : null}
            {section === "plans" ? <PlansSection {...sectionProps} /> : null}
            {section === "review" ? (
              <ReviewSection
                draft={draft}
                academicYear={inventory.academic_year.label}
                formRevision={`${inventory.form_revision.official_code} · Revision ${inventory.form_revision.official_revision}`}
                issues={issues}
                programLookupReady={Boolean(programQuery.data) || !canDiscoverPrograms}
                onSelectIssue={selectIssue}
              />
            ) : null}
          </fieldset>

          <div className="mt-8 border-t border-border pt-5">
            {dirty ? (
              <p role="status" className="mb-4 text-sm font-semibold text-warning">Unsaved changes</p>
            ) : (
              <p role="status" className="mb-4 text-sm text-muted">Saved</p>
            )}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  disabled={pending || !dirty}
                  onClick={() => void saveProgress(false)}
                >
                  {save.isPending ? "Saving…" : "Save progress"}
                </Button>
                {section !== "review" ? (
                  <Button
                    variant="secondary"
                    disabled={pending}
                    onClick={() => void saveProgress(true)}
                  >
                    {save.isPending ? "Saving…" : "Save & continue"}
                  </Button>
                ) : (
                  <Button
                    disabled={pending || dirty || issues.length > 0}
                    onClick={() => setConfirmSubmit(true)}
                  >
                    {submitPending ? "Submitting…" : dirty ? "Save progress before submit" : "Submit Individual Inventory"}
                  </Button>
                )}
              </div>
              <div className="flex justify-between gap-2 sm:justify-end">
                <Button
                  variant="quiet"
                  disabled={pending || currentSectionIndex <= 0}
                  onClick={() => navigateToSection(inventorySections[currentSectionIndex - 1].id)}
                >
                  Previous section
                </Button>
                {section !== "review" ? (
                  <Button
                    variant="quiet"
                    disabled={pending}
                    onClick={() => navigateToSection(inventorySections[currentSectionIndex + 1].id)}
                  >
                    Next section
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      <ConsequentialActionDialog
        open={confirmSubmit}
        title={`Submit your Individual Inventory for Academic Year ${inventory.academic_year.label}?`}
        confirmLabel="Submit Individual Inventory"
        pendingLabel="Submitting…"
        pending={submitPending}
        confirmDisabled={dirty || issues.length > 0}
        error={submitError}
        onOpenChange={setConfirmSubmit}
        onConfirm={() => void submitInventory()}
      >
        <p>
          After submission, this Inventory becomes read-only. An authorized
          Counselor may reopen the current-year record if corrections are
          needed.
        </p>
      </ConsequentialActionDialog>
    </section>
  );
}
