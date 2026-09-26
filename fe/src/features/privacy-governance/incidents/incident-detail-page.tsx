"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  incidentChanges,
  incidentFieldLabels,
  IncidentForm,
  incidentFormValues,
  type IncidentFormValues,
} from "@/features/privacy-governance/incidents/incident-form";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import { notificationAssessmentLabels } from "@/features/privacy-governance/privacy-governance-presentation";
import {
  ActionMessages,
  CategoryList,
  DetailSection,
  IncidentStatusBadge,
  invalidatePrivacyRecords,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyRecordUnavailable,
  privacyPaths,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import { formatDateTime } from "@/lib/date-time";
import {
  IncidentStatusValue,
  type PrivacyIncidentResponse,
} from "@/lib/api/generated/model";
import { getOverviewGetSummaryQueryKey } from "@/lib/api/generated/overview/overview";
import {
  usePrivacyGovernanceGetIncident,
  usePrivacyGovernanceResolveIncident,
  usePrivacyGovernanceUpdateIncident,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

function IncidentEditor({
  incident,
  onDone,
}: {
  incident: PrivacyIncidentResponse;
  onDone: (saved: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const update = usePrivacyGovernanceUpdateIncident();
  const action = usePrivacyAction(incidentFieldLabels);
  const [baseline] = useState(() => incidentFormValues(incident));

  async function submit(values: IncidentFormValues) {
    const changes = incidentChanges(baseline, values);
    if (!changes.ok) {
      action.setNotice(null);
      action.setError(changes.error);
      return;
    }
    if (Object.keys(changes.value).length === 0) {
      action.setError(null);
      action.setNotice("No changes to save.");
      return;
    }
    const result = await action.run(
      () => update.mutateAsync({ incidentId: incident.id, data: changes.value }),
      "The privacy incident could not be saved.",
    );
    if (!result) return;
    await invalidatePrivacyRecords(queryClient, privacyPaths.incidents);
    void queryClient.invalidateQueries({ queryKey: getOverviewGetSummaryQueryKey() });
    onDone(true);
  }

  return (
    <>
      <IncidentForm
        initial={baseline}
        pending={update.isPending}
        submitLabel="Save changes"
        pendingLabel="Saving…"
        messages={<ActionMessages error={action.error} notice={action.notice} />}
        cancel={
          <Button variant="secondary" disabled={update.isPending} onClick={() => onDone(false)}>
            Cancel
          </Button>
        }
        onSubmit={(values) => void submit(values)}
      />
      {action.stepUpDialog}
    </>
  );
}

function OptionalText({ value }: { value: string }) {
  return value ? (
    <p className="break-words text-sm text-ink">{value}</p>
  ) : (
    <p className="text-sm text-muted">None recorded.</p>
  );
}

export function IncidentDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const searchParams = useSearchParams();
  const { canManage } = usePrivacyAccess();
  const queryClient = useQueryClient();
  const detail = usePrivacyGovernanceGetIncident(incidentId, { query: { retry: false } });
  const resolve = usePrivacyGovernanceResolveIncident();
  const action = usePrivacyAction();
  const [editing, setEditing] = useState(false);
  const [resolveOpen, setResolveOpen] = useState(false);

  if (detail.isPending) return <PrivacyDetailSkeleton label="Loading privacy incident…" />;
  if (detail.isError) {
    return (
      <PrivacyRecordUnavailable
        title="Privacy incident unavailable"
        error={detail.error}
        fallback="The privacy incident could not be loaded."
        backHref="/portal/privacy/incidents"
        backLabel="Privacy Incidents"
        onRetry={() => void detail.refetch()}
      />
    );
  }

  const incident = detail.data.data;
  const resolved = incident.status === IncidentStatusValue.RESOLVED;
  const manageable = canManage && !resolved;

  async function confirmResolve() {
    const result = await action.run(
      () => resolve.mutateAsync({ incidentId }),
      "The privacy incident could not be resolved.",
      { onStepUpRequired: () => setResolveOpen(false) },
    );
    if (!result) return;
    setResolveOpen(false);
    action.setNotice("Privacy incident resolved.");
    void invalidatePrivacyRecords(queryClient, privacyPaths.incidents);
    void queryClient.invalidateQueries({ queryKey: getOverviewGetSummaryQueryKey() });
  }

  return (
    <article>
      <PrivacyPageHeader
        title={incident.title}
        context={<span className="font-mono text-ink">{incident.reference_code}</span>}
        backHref="/portal/privacy/incidents"
        backLabel="Privacy Incidents"
        meta={
          <>
            <IncidentStatusBadge status={incident.status} />
            <span>Updated {formatDateTime(incident.updated_at)}</span>
          </>
        }
        action={
          manageable && !editing ? (
            <>
              <Button
                variant="secondary"
                onClick={() => {
                  action.reset();
                  setEditing(true);
                }}
              >
                Edit
              </Button>
              <Button
                onClick={() => {
                  action.reset();
                  setResolveOpen(true);
                }}
              >
                Resolve incident
              </Button>
            </>
          ) : null
        }
      />

      {searchParams.get("created") === "1" && !editing ? (
        <p role="status" className="mb-4 text-sm text-success">
          Privacy incident recorded.
        </p>
      ) : null}
      <ActionMessages
        error={resolveOpen ? null : action.error}
        notice={action.notice}
        className="mb-4"
      />

      {editing ? (
        <IncidentEditor
          key={incident.updated_at}
          incident={incident}
          onDone={(saved) => {
            setEditing(false);
            if (saved) action.setNotice("Privacy incident updated.");
          }}
        />
      ) : (
        <div className="max-w-4xl divide-y divide-border border-y border-border">
          <DetailSection title="What happened">
            <PlainTextBlock text={incident.summary} />
            <dl className="mt-4 grid max-w-3xl gap-4">
              <div>
                <dt className="text-xs font-semibold text-muted">Affected area</dt>
                <dd className="mt-1 break-words text-sm text-ink">{incident.affected_area}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-muted">Personal data categories</dt>
                <dd className="mt-2">
                  <CategoryList items={incident.personal_data_categories} />
                </dd>
              </div>
            </dl>
          </DetailSection>
          <DetailSection title="Timing">
            <dl className="grid max-w-3xl gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-semibold text-muted">Occurred</dt>
                <dd className="mt-1 text-sm text-ink">
                  {incident.occurred_at ? (
                    formatDateTime(incident.occurred_at)
                  ) : (
                    <span className="text-muted">Not recorded</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-muted">Discovered</dt>
                <dd className="mt-1 text-sm text-ink">
                  {formatDateTime(incident.discovered_at)}
                </dd>
              </div>
            </dl>
          </DetailSection>
          <DetailSection title="Assessment">
            <dl className="mb-4">
              <dt className="text-xs font-semibold text-muted">Estimated affected people</dt>
              <dd className="mt-1 text-sm text-ink">
                {incident.estimated_affected_subjects ?? (
                  <span className="text-muted">Not recorded</span>
                )}
              </dd>
            </dl>
            <PlainTextBlock text={incident.assessment_summary} />
          </DetailSection>
          <DetailSection title="Containment">
            <PlainTextBlock text={incident.containment_summary} />
          </DetailSection>
          <DetailSection title="Notification">
            <dl className="grid max-w-3xl gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-semibold text-muted">Notification assessment</dt>
                <dd className="mt-1 text-sm text-ink">
                  {notificationAssessmentLabels[incident.notification_assessment]}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-muted">Notification reference</dt>
                <dd className="mt-1">
                  <OptionalText value={incident.notification_reference} />
                </dd>
              </div>
            </dl>
          </DetailSection>
          <DetailSection title="Record">
            <dl className="grid max-w-3xl gap-4 sm:grid-cols-3">
              <div>
                <dt className="text-xs font-semibold text-muted">Recorded</dt>
                <dd className="mt-1 text-sm text-ink">{formatDateTime(incident.created_at)}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-muted">Updated</dt>
                <dd className="mt-1 text-sm text-ink">{formatDateTime(incident.updated_at)}</dd>
              </div>
              {incident.resolved_at ? (
                <div>
                  <dt className="text-xs font-semibold text-muted">Resolved</dt>
                  <dd className="mt-1 text-sm text-ink">
                    {formatDateTime(incident.resolved_at)}
                  </dd>
                </div>
              ) : null}
            </dl>
          </DetailSection>
        </div>
      )}

      <PrivacyConfirmDialog
        open={resolveOpen}
        title="Resolve this privacy incident?"
        description={
          <p>Resolved incidents cannot be edited through the ordinary workflow.</p>
        }
        confirmLabel="Resolve incident"
        pendingLabel="Resolving…"
        pending={resolve.isPending}
        error={resolveOpen ? action.error : null}
        onOpenChange={(open) => {
          setResolveOpen(open);
          if (!open) action.setError(null);
        }}
        onConfirm={() => void confirmResolve()}
      />
      {action.stepUpDialog}
    </article>
  );
}
