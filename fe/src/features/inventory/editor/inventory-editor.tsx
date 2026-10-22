"use client";

import { studentActionsQueryFamily } from "@/features/student-actions/student-actions-data";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { FormSaveStatus, FormSectionNavigation } from "@/components/ui/form-experience";
import { Panel, PanelHeader, PanelFooter, PanelMessage } from "@/components/ui/panel";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { BackgroundSection } from "@/features/inventory/editor/background-section";
import { EducationSection } from "@/features/inventory/editor/education-section";
import { FamilySection } from "@/features/inventory/editor/family-section";
import { HealthSection } from "@/features/inventory/editor/health-section";
import { InterestsSection } from "@/features/inventory/editor/interests-section";
import { InventoryReviewProvider } from "@/features/inventory/editor/inventory-review-context";
import { OrganizationsSection } from "@/features/inventory/editor/organizations-section";
import { PersonalSection } from "@/features/inventory/editor/personal-section";
import { PlansSection } from "@/features/inventory/editor/plans-section";
import { ReviewSection } from "@/features/inventory/editor/review-section";
import { InventoryCorrectionNotice } from "@/features/inventory/inventory-correction-notice";
import {
  focusInventoryCorrectionTarget,
  INVENTORY_SECTION_REVIEW_ID,
  INVENTORY_SECTION_START_ID,
  inventoryCorrectionTarget,
  inventoryCorrectionFocusOrder,
  inventoryReviewHints,
  inventoryReviewHintText,
  readInventoryCorrectionTargets,
} from "@/features/inventory/inventory-correction-targets";
import { getInventoryDraftIssues, getInventorySubmissionIssues, normalizeInventoryPayload, toInventoryPayload, type InventorySubmissionIssue } from "@/features/inventory/inventory-payload";
import { inventorySections, type InventorySectionId } from "@/features/inventory/inventory-presentation";
import { InventoryHeading, InventoryNotice, inventoryErrorMessage } from "@/features/inventory/inventory-shared";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import type { InventoryCorrectionTarget, InventoryPayload, InventoryResponse } from "@/lib/api/generated/model";
import {
  getInventoryGetMyCurrentQueryKey,
  getInventoryGetMyStatusQueryKey,
  getInventoryListMyHistoryQueryKey,
  useInventorySubmitMyCurrent,
  useInventoryUpdateMyCurrent,
} from "@/lib/api/generated/inventory/inventory";
import { useOrganizationListPrograms } from "@/lib/api/generated/organization/organization";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function InventoryEditor({
  inventory,
  refreshNotice,
}: {
  inventory: InventoryResponse;
  // Shown when the page could not refresh the record; the editor keeps its draft.
  refreshNotice?: ReactNode;
}) {
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
  const selectedProgram = activePrograms.find((program) => program.id === draft.program_id) ?? null;
  const [section, setSection] = useState<InventorySectionId>("personal");
  const [validationVisible, setValidationVisible] = useState(false);
  const pendingTargetRef = useRef<string | null>(null);
  // The element ids to try for a correction target the Student chose, best first.
  const pendingReviewRef = useRef<string[] | null>(null);
  // Bumped on every request to show an issue, so its field gets focus even within the open section.
  const [focusRequest, setFocusRequest] = useState(0);
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
  const issues = getInventorySubmissionIssues(draft, activeProgramIds, activePrograms);
  const currentSectionIndex = inventorySections.findIndex((item) => item.id === section);
  const currentCorrection = inventory.correction_pending ? inventory.latest_correction : null;
  const correctionTargetValues = currentCorrection?.targets;
  const correctionTargets = useMemo(
    () => readInventoryCorrectionTargets(correctionTargetValues).targets,
    [correctionTargetValues],
  );
  // Advisory only: a target never marks an answer invalid, blocks saving, or blocks resubmission.
  const reviewHints = useMemo(() => inventoryReviewHints(correctionTargets, draft), [correctionTargets, draft]);

  useEffect(() => {
    const pendingReview = pendingReviewRef.current;
    if (pendingReview) {
      pendingReviewRef.current = null;
      focusInventoryCorrectionTarget(pendingReview);
      return;
    }
    const pendingTargetId = pendingTargetRef.current;
    if (!pendingTargetId) return;
    pendingTargetRef.current = null;
    const target = document.getElementById(pendingTargetId);
    if (!target) return;
    target.scrollIntoView({ block: "center" });
    const focusTarget = target.matches("input, select, textarea, button, [tabindex]")
      ? target
      : target.querySelector<HTMLElement>("input, select, textarea, button");
    (focusTarget as HTMLElement | null)?.focus({ preventScroll: true });
  }, [section, focusRequest]);

  function navigateToSection(next: InventorySectionId, focusSection = true) {
    if (focusSection) pendingTargetRef.current = INVENTORY_SECTION_START_ID;
    if (next === "review") setValidationVisible(true);
    setSection(next);
    if (focusSection) setFocusRequest((current) => current + 1);
  }

  function selectCorrectionTarget(target: InventoryCorrectionTarget) {
    pendingReviewRef.current = inventoryCorrectionFocusOrder(target, draft);
    setSection(inventoryCorrectionTarget(target).section);
    setFocusRequest((current) => current + 1);
  }

  function selectIssue(issue: InventorySubmissionIssue) {
    setValidationVisible(true);
    pendingTargetRef.current = issue.targetId;
    setSection(issue.section);
    setFocusRequest((current) => current + 1);
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
      void queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() });
      void queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() });
    }
    if (code === "inventory_conflict") {
      // Reload the annual status and history, but not the record this editor started from: a
      // reload could replace the editor and lose answers that were not saved. The broad conflict
      // code does not identify a safe field-specific reason, so keep the frontend guidance.
      void queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() });
      void queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() });
      void queryClient.invalidateQueries({ queryKey: getInventoryListMyHistoryQueryKey() });
      return `${message} Your answers are kept on this page.`;
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
    const draftIssues = getInventoryDraftIssues(draft);
    if (draftIssues.length > 0) {
      setSaveError(draftIssues[0].message);
      selectIssue(draftIssues[0]);
      return false;
    }
    try {
      const response = await save.mutateAsync({ data: normalizeInventoryPayload(draft) });
      const canonical = toInventoryPayload(response.data);
      setDraft(canonical);
      setSaved(canonical);
      queryClient.setQueryData(getInventoryGetMyCurrentQueryKey(), response);
      void queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() });
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
        queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() }),
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
      {refreshNotice}

      <div className="mt-4 max-w-3xl space-y-2 text-sm leading-6 text-muted">
        <p>Your Individual Inventory helps the Guidance and Counseling Office understand your needs and future plans. Please provide accurate information. Your responses are handled as confidential Student information.</p>
        <p>Move between sections in any order. Save progress before leaving.</p>
      </div>

      {currentCorrection ? (
        <div className="mt-5">
          <InventoryCorrectionNotice correction={currentCorrection} onSelectTarget={selectCorrectionTarget} />
        </div>
      ) : null}

      <div data-inventory-workspace="" className="@container/inventory-workspace mt-5 min-w-0">
        <div className="grid min-w-0 items-start gap-4 @[42rem]/inventory-workspace:grid-cols-[13rem_minmax(0,1fr)] @[42rem]/inventory-workspace:gap-6">
        <div data-inventory-navigation="" className="min-w-0 mb-0 @[42rem]/inventory-workspace:sticky @[42rem]/inventory-workspace:top-5">
          <FormSectionNavigation
            id="inventory-section-select"
            label="Inventory section"
            navigationLabel="Individual Inventory sections"
            sections={inventorySections.map((item) => ({
              ...item,
              attentionCount: validationVisible ? issues.filter((issue) => item.id === "review" || issue.section === item.id).length : undefined,
            }))}
            current={section}
            onSelect={navigateToSection}
          />
        </div>

        <Panel as="div" data-inventory-panel="" className="min-w-0">
          {/* Where focus lands when a requested answer cannot take it, such as while saving. */}
          <div id={INVENTORY_SECTION_START_ID} tabIndex={-1} className="rounded-t-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus">
            <PanelHeader
              title={inventorySections[currentSectionIndex]?.label}
              titleId="inventory-editor-heading"
              context={`Section ${currentSectionIndex + 1} of ${inventorySections.length}`}
            />
          </div>

          {saveError || submitError ? (
            <div className="border-b border-brand-line">
              {saveError ? <PanelMessage tone="danger" role="alert">{saveError}</PanelMessage> : null}
              {submitError ? <PanelMessage tone="danger" role="alert">{submitError}</PanelMessage> : null}
            </div>
          ) : null}

          {/* Field columns follow the sheet width, including when text size grows. */}
          <fieldset disabled={pending} className="@container/inventory min-w-0 px-4 py-5 [overflow-wrap:anywhere] disabled:opacity-100 sm:px-5">
            <InventoryReviewProvider value={reviewHints}>
              {section !== "review" && reviewHints.sections.has(section) ? (
                <p id={INVENTORY_SECTION_REVIEW_ID} tabIndex={-1} className="mb-5 rounded-sm text-sm font-medium leading-6 text-info focus:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                  {inventoryReviewHintText.section}
                </p>
              ) : null}
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
                  selectedProgram={selectedProgram}
                  onSelectIssue={selectIssue}
                  onSelectSection={navigateToSection}
                />
              ) : null}
            </InventoryReviewProvider>
          </fieldset>

          <PanelFooter className="block space-y-3">
            <FormSaveStatus dirty={dirty} saving={save.isPending} savedMessage={notice} />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 flex-wrap gap-2 *:max-w-full">
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
              <div className="flex min-w-0 flex-wrap gap-2 *:max-w-full">
                <Button
                  variant="secondary"
                  disabled={pending || currentSectionIndex <= 0}
                  onClick={() => navigateToSection(inventorySections[currentSectionIndex - 1].id)}
                >
                  Back
                </Button>
                {section !== "review" ? (
                  <Button
                    variant="primary"
                    disabled={pending}
                    onClick={() => navigateToSection(inventorySections[currentSectionIndex + 1].id)}
                  >
                    {inventorySections[currentSectionIndex + 1].id === "review" ? "Review answers" : "Continue"}
                  </Button>
                ) : null}
              </div>
            </div>
          </PanelFooter>
        </Panel>
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
