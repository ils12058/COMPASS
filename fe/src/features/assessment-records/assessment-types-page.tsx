"use client";

import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useRef, useState, type FormEvent } from "react";
import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { dataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import {
  Panel,
  PanelBody,
  PanelFooter,
  PanelHeader,
  PanelMessage,
} from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useAssessmentRecordsCreateType,
  useAssessmentRecordsListTypes,
  useAssessmentRecordsUpdateType,
} from "@/lib/api/generated/assessment-records/assessment-records";
import type { AssessmentTypeResponse } from "@/lib/api/generated/model";
import { getAssessmentRecordsAccess } from "./assessment-records-access";
import {
  assessmentErrorMessage,
  AssessmentError,
  AssessmentLoading,
  AssessmentUnavailable,
  useAssessmentRefresh,
} from "./assessment-records-shared";

export function AssessmentTypesPage() {
  const { user } = usePortalSession();
  const allowed = getAssessmentRecordsAccess(user).canManageTypes;
  const query = useAssessmentRecordsListTypes(undefined, {
    query: { enabled: allowed, retry: false },
  });
  if (!allowed) return <AssessmentUnavailable />;
  const types = safeQueryData(query)?.data;
  if (!types)
    return query.isPending ? (
      <AssessmentLoading />
    ) : (
      <AssessmentError
        error={query.error}
        retry={() => void query.refetch()}
        pending={query.isFetching}
      />
    );
  return (
    <AssessmentTypeCatalog
      types={types}
      refreshError={query.isError}
      retry={() => void query.refetch()}
      refreshing={query.isFetching}
    />
  );
}

function AssessmentTypeCatalog({
  types,
  refreshError,
  retry,
  refreshing,
}: {
  types: AssessmentTypeResponse[];
  refreshError: boolean;
  retry: () => void;
  refreshing: boolean;
}) {
  const [editing, setEditing] = useState<AssessmentTypeResponse | null>(null);
  const [draft, setDraft] = useState({ name: "", description: "" });
  const [error, setError] = useState<string | null>(null);
  const [transition, setTransition] = useState<AssessmentTypeResponse | null>(
    null,
  );
  const [transitionError, setTransitionError] = useState<string | null>(null);
  const create = useAssessmentRecordsCreateType();
  const update = useAssessmentRecordsUpdateType();
  const refresh = useAssessmentRefresh();
  const status = useActionStatus();
  const lock = useRef(false);
  const nameInput = useRef<HTMLInputElement>(null);
  const pending = create.isPending || update.isPending;
  const dirty =
    draft.name !== (editing?.name ?? "") ||
    draft.description !== (editing?.description ?? "");
  useUnsavedChangesGuard({
    dirty,
    message: "Your Assessment Type changes have not been saved.",
  });
  function select(type: AssessmentTypeResponse | null) {
    if (
      dirty &&
      !window.confirm("Discard your unsaved Assessment Type changes?")
    )
      return;
    setEditing(type);
    setDraft({ name: type?.name ?? "", description: type?.description ?? "" });
    setError(null);
    nameInput.current?.focus();
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current) return;
    if (!draft.name.trim()) {
      setError("Enter an Assessment Type name.");
      return;
    }
    lock.current = true;
    setError(null);
    try {
      if (editing)
        await update.mutateAsync({ typeId: editing.id, data: draft });
      else await create.mutateAsync({ data: draft });
      setEditing(null);
      setDraft({ name: "", description: "" });
      status.show(
        editing ? "Assessment Type updated." : "Assessment Type created.",
      );
      await refresh();
    } catch (failure) {
      setError(assessmentErrorMessage(failure));
    } finally {
      lock.current = false;
    }
  }
  async function changeActive() {
    if (!transition || lock.current) return;
    lock.current = true;
    setTransitionError(null);
    try {
      await update.mutateAsync({
        typeId: transition.id,
        data: { is_active: !transition.is_active },
      });
      status.show(
        transition.is_active
          ? "Assessment Type deactivated."
          : "Assessment Type reactivated.",
      );
      setTransition(null);
      await refresh();
    } catch (failure) {
      setTransitionError(assessmentErrorMessage(failure));
    } finally {
      lock.current = false;
    }
  }
  return (
    <>
      <PageHeader
        title="Assessment Types"
        back={
          <Link href="/portal/assessment-records" className={pageBackLinkClass}>
            Back to Assessment Records
          </Link>
        }
        description="Institutional catalog managed by Head Guidance. Deactivating a type prevents new use and preserves historical records."
      />
      {refreshError ? (
        <RefreshFailureNotice onRetry={retry} retrying={refreshing} />
      ) : null}
      <div className="space-y-5">
        <Panel aria-labelledby="assessment-type-catalog">
          <PanelHeader
            title="Assessment Types"
            titleId="assessment-type-catalog"
            context={`${types.length} ${types.length === 1 ? "type" : "types"}`}
          />
          {types.length ? (
            <div className="max-w-full overflow-x-auto">
              <table className={dataTable.table}>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={dataTable.headerCell}>
                      Type
                    </th>
                    <th scope="col" className={dataTable.headerCell}>
                      Availability
                    </th>
                    <th scope="col" className={dataTable.headerCell}>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {types.map((type) => (
                    <tr key={type.id} className={dataTable.row}>
                      <td className={dataTable.cell}>
                        <span className="font-semibold">{type.name}</span>
                        {type.description ? (
                          <p className="mt-1 max-w-xl whitespace-pre-wrap [overflow-wrap:anywhere] text-sm text-muted">
                            {type.description}
                          </p>
                        ) : null}
                      </td>
                      <td className={dataTable.cell}>
                        {type.is_active ? "Active" : "Inactive"}
                      </td>
                      <td className={dataTable.cell}>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="quiet"
                            disabled={pending}
                            onClick={() => select(type)}
                            aria-label={`Edit ${type.name}`}
                          >
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            disabled={pending}
                            aria-label={`${type.is_active ? "Deactivate" : "Reactivate"} ${type.name}`}
                            onClick={() => {
                              setTransition(type);
                              setTransitionError(null);
                            }}
                          >
                            {type.is_active ? "Deactivate" : "Reactivate"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <PanelMessage>
              No Assessment Types have been configured.
            </PanelMessage>
          )}
        </Panel>
        <Panel>
          <PanelHeader
            title={editing ? "Edit Assessment Type" : "Create Assessment Type"}
          />
          <form
            aria-label={
              editing ? "Edit Assessment Type" : "Create Assessment Type"
            }
            onSubmit={(event) => void save(event)}
          >
            <PanelBody>
              <fieldset disabled={pending} className="space-y-4">
                <div>
                  <Label htmlFor="assessment-type-name">Name</Label>
                  <Input
                    ref={nameInput}
                    id="assessment-type-name"
                    required
                    maxLength={160}
                    value={draft.name}
                    onChange={(event) =>
                      setDraft((value) => ({
                        ...value,
                        name: event.target.value,
                      }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="assessment-type-description">
                    Description (optional)
                  </Label>
                  <Textarea
                    id="assessment-type-description"
                    maxLength={2000}
                    rows={3}
                    value={draft.description}
                    onChange={(event) =>
                      setDraft((value) => ({
                        ...value,
                        description: event.target.value,
                      }))
                    }
                  />
                </div>
              </fieldset>
              {error ? (
                <Notice className="mt-4" role="alert" tone="danger">
                  {error}
                </Notice>
              ) : null}
            </PanelBody>
            <PanelFooter>
              <Button type="submit" disabled={pending}>
                {pending ? "Saving…" : editing ? "Save type" : "Create type"}
              </Button>
              {editing ? (
                <Button
                  type="button"
                  variant="quiet"
                  disabled={pending}
                  onClick={() => select(null)}
                >
                  Cancel edit
                </Button>
              ) : null}
            </PanelFooter>
          </form>
        </Panel>
      </div>
      <ConsequentialActionDialog
        open={Boolean(transition)}
        title={`${transition?.is_active ? "Deactivate" : "Reactivate"} Assessment Type`}
        confirmLabel={
          transition?.is_active ? "Deactivate type" : "Reactivate type"
        }
        pendingLabel="Saving…"
        pending={pending}
        error={transitionError}
        onOpenChange={(open) => {
          if (!open) setTransition(null);
        }}
        onConfirm={() => void changeActive()}
      >
        <p>
          {transition?.is_active
            ? `${transition.name} will no longer be available for new records. Historical records remain readable.`
            : `${transition?.name} will become available for new records.`}
        </p>
      </ConsequentialActionDialog>
      <ActionStatus status={status.status} onDismiss={status.dismiss} />
    </>
  );
}
