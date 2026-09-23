"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InstitutionActionFeedback, InstitutionWorkspaceUnavailable } from "@/features/institution-configuration/institution-shared";
import { canManageAcademicYears, canViewAcademicYears } from "@/features/institution-configuration/institution-access";
import { useInstitutionConfigurationAction, institutionConfigurationErrorMessage } from "@/features/institution-configuration/institution-action";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getAcademicYearsListQueryKey,
  useAcademicYearsCreate,
  useAcademicYearsList,
  useAcademicYearsSetCurrent,
} from "@/lib/api/generated/academic-years/academic-years";
import type { AcademicYearResponse } from "@/lib/api/generated/model";
import { Skeleton } from "@/components/ui/skeleton";

export function AcademicYearsPage() {
  const { user } = usePortalSession();

  if (!canViewAcademicYears(user)) {
    return <InstitutionWorkspaceUnavailable workspace="Academic Years" />;
  }

  return <AcademicYearsWorkspace canManage={canManageAcademicYears(user)} />;
}

function AcademicYearsWorkspace({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const years = useAcademicYearsList();
  const createYear = useAcademicYearsCreate();
  const setCurrentYear = useAcademicYearsSetCurrent();
  const action = useInstitutionConfigurationAction();
  const [createOpen, setCreateOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmYear, setConfirmYear] = useState<AcademicYearResponse | null>(null);
  const [pageNotice, setPageNotice] = useState<string | null>(null);

  const items = years.data?.data.items ?? [];
  const currentYear = items.find((year) => year.is_current);

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedLabel = label.trim();
    if (!submittedLabel || submittedLabel.length > 32) {
      action.setError("Enter an Academic Year label of up to 32 characters.");
      return;
    }

    const created = await action.run(
      () => createYear.mutateAsync({ data: { label: submittedLabel } }),
      "The Academic Year could not be added.",
      {
        onStepUpRequired: () => setCreateOpen(false),
        onStepUpVerified: () => setCreateOpen(true),
      },
    );
    if (!created) return;

    setCreateOpen(false);
    setLabel("");
    setPageNotice(
      `${created.data.label} was added. Set it as current separately when appropriate.`,
    );
    await queryClient.invalidateQueries({
      queryKey: getAcademicYearsListQueryKey(),
    });
  }

  async function confirmSetCurrent() {
    if (!confirmYear) return;
    const target = confirmYear;
    const updated = await action.run(
      () => setCurrentYear.mutateAsync({ academicYearId: target.id }),
      "The current Academic Year could not be changed.",
      {
        onStepUpRequired: () => setConfirmOpen(false),
        onStepUpVerified: () => setConfirmOpen(true),
      },
    );
    if (!updated) return;

    setConfirmOpen(false);
    setConfirmYear(null);
    setPageNotice(`${updated.data.label} is now the current Academic Year.`);
    await queryClient.invalidateQueries({
      queryKey: getAcademicYearsListQueryKey(),
    });
  }

  function openSetCurrent(year: AcademicYearResponse) {
    setPageNotice(null);
    action.resetFeedback();
    setConfirmYear(year);
    setConfirmOpen(true);
  }

  return (
    <>
      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          if (createYear.isPending) return;
          setCreateOpen(open);
          if (open) setPageNotice(null);
          action.resetFeedback();
        }}
      >
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
              Academic Years
            </h1>
            {canManage ? (
              <DialogTrigger asChild>
                <Button>Add Academic Year</Button>
              </DialogTrigger>
            ) : null}
          </div>

      {pageNotice ? (
        <p role="status" className="mt-5 text-sm leading-6 text-success">
          {pageNotice}
        </p>
      ) : null}
      {years.isError && years.data ? (
        <p role="alert" className="mt-4 text-sm leading-6 text-danger">
          Academic Years could not be refreshed. The displayed data may be out of date.
        </p>
      ) : null}

      {years.isError && !years.data ? (
        <p role="alert" className="mt-6 border-y border-danger/30 py-4 text-sm leading-6 text-danger">
          {institutionConfigurationErrorMessage(
            years.error,
            "Academic Years could not be loaded. Try again.",
          )}
        </p>
      ) : (
        <>
          <section
            aria-labelledby="current-academic-year-heading"
            className="mt-8 border-y border-border py-5"
          >
            <h2
              id="current-academic-year-heading"
              className="text-sm font-semibold text-muted"
            >
              Current Academic Year
            </h2>
            {years.isPending ? (
              <Skeleton className="mt-3 h-7 w-48" />
            ) : currentYear ? (
              <p className="mt-2 font-heading text-2xl font-semibold text-ink">
                {currentYear.label}
              </p>
            ) : (
              <>
                <p className="mt-2 font-semibold text-ink">
                  No current Academic Year is configured.
                </p>
                {!canManage ? null : (
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
                    Select an existing Academic Year or create one before workflows that require the current Academic Year can continue.
                  </p>
                )}
              </>
            )}
          </section>

          <section aria-labelledby="academic-year-list-heading" className="mt-8">
            <h2
              id="academic-year-list-heading"
              className="font-heading text-xl font-semibold text-ink"
            >
              Academic years
            </h2>
            {years.isPending ? (
              <div className="mt-4 space-y-3" aria-busy="true">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
                <p className="sr-only">Loading Academic Years…</p>
              </div>
            ) : items.length === 0 ? (
              <p className="mt-4 border-y border-border py-5 text-sm text-muted">
                No Academic Years have been configured yet.
              </p>
            ) : (
              <ul className="mt-3 border-y border-border">
                {items.map((year) => (
                  <li
                    key={year.id}
                    className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-border py-4 last:border-b-0"
                  >
                    <div className="min-w-0">
                      <p className="break-words font-semibold text-ink">
                        {year.label}
                      </p>
                      {year.is_current ? (
                        <p className="mt-1 text-sm font-semibold text-success">
                          Current
                        </p>
                      ) : null}
                    </div>
                    {canManage && !year.is_current ? (
                      <Button
                        variant="secondary"
                        disabled={setCurrentYear.isPending}
                        onClick={() => openSetCurrent(year)}
                      >
                        Set as current
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

        <DialogContent
          onEscapeKeyDown={(event) => {
            if (createYear.isPending) event.preventDefault();
          }}
          onPointerDownOutside={(event) => {
            if (createYear.isPending) event.preventDefault();
          }}
        >
          <DialogTitle>Add Academic Year</DialogTitle>
          <DialogDescription>
            The new Academic Year will not become current automatically.
          </DialogDescription>
          <form className="mt-6 space-y-5" onSubmit={submitCreate}>
            <div className="grid gap-2">
              <Label htmlFor="academic-year-label">Label</Label>
              <Input
                id="academic-year-label"
                autoComplete="off"
                maxLength={32}
                required
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                aria-invalid={action.error ? true : undefined}
                aria-describedby={
                  action.error
                    ? "academic-year-label-help academic-year-create-error"
                    : "academic-year-label-help"
                }
                disabled={createYear.isPending}
              />
              <p id="academic-year-label-help" className="text-sm text-muted">
                Up to 32 characters. Example: 2026-2027. Leading and trailing spaces are removed when saved.
              </p>
            </div>
            <InstitutionActionFeedback
              error={action.error}
              notice={action.notice}
              errorId="academic-year-create-error"
            />
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="secondary"
                disabled={createYear.isPending}
                onClick={() => {
                  setCreateOpen(false);
                  action.resetFeedback();
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createYear.isPending}>
                {createYear.isPending ? "Adding…" : "Add Academic Year"}
              </Button>
            </div>
          </form>
        </DialogContent>
        </>
      </Dialog>

      <AlertDialog
        open={confirmOpen}
        onOpenChange={(open) => {
          if (setCurrentYear.isPending) return;
          setConfirmOpen(open);
          if (!open) {
            setConfirmYear(null);
            action.resetFeedback();
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle className="break-words">
            Set {confirmYear?.label ?? "this Academic Year"} as the current Academic Year?
          </AlertDialogTitle>
          <AlertDialogDescription>
            New annual workflows will resolve against this Academic Year. Existing records remain associated with the Academic Year in which they were created. Students may need to complete a new current-year Individual Inventory before workflows that require it can continue.
          </AlertDialogDescription>
          <InstitutionActionFeedback
            error={action.error}
            notice={action.notice}
          />
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button
                variant="secondary"
                disabled={setCurrentYear.isPending}
                onClick={() => {
                  setConfirmOpen(false);
                  setConfirmYear(null);
                  action.resetFeedback();
                }}
              >
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              disabled={!confirmYear || setCurrentYear.isPending}
              onClick={() => void confirmSetCurrent()}
            >
              {setCurrentYear.isPending ? "Setting as current…" : "Set as current"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      {action.stepUpDialog}
    </>
  );
}
