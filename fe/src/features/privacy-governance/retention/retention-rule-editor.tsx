"use client";

import { RetentionHelp } from "@/features/privacy-governance/retention/retention-help";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Notice } from "@/components/ui/notice";
import {
  Panel,
  PanelBody,
  PanelFooter,
  PanelHeader,
} from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { pageSheetWidth } from "@/components/ui/page-width";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import {
  usePrivacyGovernanceActivateRetentionRule,
  usePrivacyGovernanceCreateRetentionRule,
  usePrivacyGovernanceGetRetentionRule,
  usePrivacyGovernanceRetentionCategories,
  usePrivacyGovernanceRetireRetentionRule,
  usePrivacyGovernanceUpdateRetentionRule,
} from "@/lib/api/generated/privacy-governance/privacy-governance";
import type { RetentionRuleResponse } from "@/lib/api/generated/model";
import { formatDateOnly } from "@/lib/institutional-time";
import {
  ActionMessages,
  FormSection,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
  usePrivacyAction,
} from "../privacy-governance-shared";
import {
  categoryLabels,
  dispositionActionLabel,
  retentionContractLabel,
  invalidateRetention,
  isRetentionConflict,
  useRetentionAccess,
} from "./retention-shared";

type RuleFormValues = {
  code: string;
  label: string;
  category: string;
  contractVersion: string;
  duration: string;
  reference: string;
  effective: string;
};
function formValues(rule?: RetentionRuleResponse): RuleFormValues {
  return {
    code: rule?.code ?? "",
    label: rule?.label ?? "",
    category: rule?.category ?? "",
    contractVersion: rule ? String(rule.contract_version) : "",
    duration: rule ? String(rule.duration_days) : "",
    reference: rule?.policy_reference ?? "",
    effective: rule?.effective_on ?? "",
  };
}

function RuleForm({
  rule,
  onSaved,
  onConflict,
  onDirty,
  fresh = true,
}: {
  rule?: RetentionRuleResponse;
  onSaved: (id: string) => void;
  onConflict?: () => Promise<unknown>;
  onDirty?: (dirty: boolean) => void;
  fresh?: boolean;
}) {
  const create = usePrivacyGovernanceCreateRetentionRule({
    mutation: { retry: false },
  });
  const update = usePrivacyGovernanceUpdateRetentionRule({
    mutation: { retry: false },
  });
  const categories = usePrivacyGovernanceRetentionCategories({
    query: { retry: false },
  });
  const action = usePrivacyAction();
  const [baseline, setBaseline] = useState(() => formValues(rule));
  const [values, setValues] = useState(baseline);
  const [reviewedRevision, setReviewedRevision] = useState(rule?.revision);
  const [changed, setChanged] = useState(false);
  const dirty = JSON.stringify(values) !== JSON.stringify(baseline);
  const needsReview =
    changed || Boolean(rule && reviewedRevision !== rule.revision);
  useEffect(() => {
    onDirty?.(dirty || needsReview);
  }, [dirty, needsReview, onDirty]);
  useUnsavedChangesGuard({
    dirty,
    message: "Discard your unsaved retention rule?",
  });
  const contracts = safeQueryData(categories)?.data ?? [];
  const categoryChoices = [...new Map(contracts.map((item) => [item.category, item])).values()];
  const selected = contracts.find(
    (item) => item.category === values.category && String(item.contract_version) === values.contractVersion,
  );
  const pending = create.isPending || update.isPending;
  function field(key: keyof RuleFormValues, value: string) {
    setValues((old) => ({ ...old, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || needsReview || !fresh) return;
    const data = {
      label: values.label,
      category: selected.category,
      contract_version: selected.contract_version,
      trigger: selected.trigger,
      action: selected.action,
      duration_days: Number(values.duration),
      policy_reference: values.reference,
      effective_on: values.effective,
    };
    const result = await action.run<{ data: RetentionRuleResponse }>(
      () =>
        rule
          ? update.mutateAsync({
              ruleId: rule.id,
              data: {
                ...data,
                expected_revision: reviewedRevision ?? rule.revision,
              },
            })
          : create.mutateAsync({ data: { ...data, code: values.code } }),
      "The retention draft could not be saved.",
      {
        onError: (caught) => {
          if (isRetentionConflict(caught) && rule) {
            setChanged(true);
            void onConflict?.();
          }
        },
      },
    );
    if (result) {
      setBaseline(values);
      setReviewedRevision(result.data.revision);
      onSaved(result.data.id);
    }
  }

  return (
    <Panel>
      <form onSubmit={(event) => void submit(event)}>
        <FormSection
          title="Institutional policy"
          description="Enter an approved duration and basis reference. Drafting does not authorize disposition."
        >
          {!rule ? (
            <div className="grid gap-2">
              <Label htmlFor="rule-code">Rule code</Label>
              <Input
                id="rule-code"
                value={values.code}
                required
                maxLength={64}
                onChange={(event) => field("code", event.target.value)}
              />
            </div>
          ) : null}
          <div className="grid gap-2">
            <Label htmlFor="rule-label">Administrative label</Label>
            <Input
              id="rule-label"
              value={values.label}
              required
              maxLength={160}
              onChange={(event) => field("label", event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="rule-category">Data category</Label>
            <Select
              id="rule-category"
              value={values.category}
              required
              disabled={categories.isError || categories.isPending}
              onChange={(event) => setValues((old) => ({ ...old, category: event.target.value, contractVersion: "" }))}
            >
              <option value="">Select category</option>
              {categoryChoices.map((item) => (
                <option key={item.category} value={item.category}>
                  {item.label}
                </option>
              ))}
            </Select>
            {categories.isError ? (
              <PrivacyQueryError
                error={categories.error}
                fallback="Supported categories could not be loaded."
                onRetry={() => void categories.refetch()}
              />
            ) : null}
          </div>
          <div className="grid gap-2">
            <Label htmlFor="rule-contract">Governance contract</Label>
            <Select id="rule-contract" value={values.contractVersion} required disabled={!values.category || categories.isError || categories.isPending} onChange={(event) => field("contractVersion", event.target.value)}>
              <option value="">Select contract</option>
              {contracts.filter((item) => item.category === values.category).map((item) => (
                <option key={item.contract_version} value={item.contract_version}>{retentionContractLabel(item.contract_version)}</option>
              ))}
            </Select>
            <p className="text-xs text-muted">Each contract governs its own records. Existing sessions retain their original media policy.</p>
          </div>
          {selected ? (
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted">Retention trigger</dt>
                <dd>
                  {selected.trigger === "SUBMITTED_AT"
                    ? "Submission timestamp"
                    : "Provider artifact ready timestamp, after the session expires"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Disposition</dt>
                <dd>
                  {dispositionActionLabel(selected.action)}
                </dd>
              </div>
            </dl>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="rule-duration">Whole elapsed days</Label>
              <Input
                id="rule-duration"
                type="number"
                min={1}
                max={365000}
                step={1}
                required
                value={values.duration}
                onChange={(event) => field("duration", event.target.value)}
              />
              <p className="text-xs text-muted">
                Each day is 24 hours from the trigger timestamp.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="rule-effective">Effective date</Label>
              <Input
                id="rule-effective"
                type="date"
                required
                value={values.effective}
                onChange={(event) => field("effective", event.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="rule-reference">Policy / basis reference</Label>
            <Input
              id="rule-reference"
              required
              maxLength={500}
              value={values.reference}
              onChange={(event) => field("reference", event.target.value)}
            />
          </div>
        </FormSection>
        {needsReview && rule ? (
          <FormSection title="Current saved draft">
            <Notice tone="warning">
              This draft changed elsewhere. Your input is kept above. Review the
              saved values before submitting again.
            </Notice>
            <dl className="grid gap-2 text-sm">
              <div>
                <dt className="text-muted">Label / category</dt>
                <dd>
                  {rule.label} · {categoryLabels[rule.category]} · {retentionContractLabel(rule.contract_version)}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Duration / effective date</dt>
                <dd>
                  {rule.duration_days} days ·{" "}
                  {formatDateOnly(rule.effective_on)}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Policy reference</dt>
                <dd>{rule.policy_reference}</dd>
              </div>
            </dl>
            <Button
              variant="secondary"
              disabled={!fresh}
              onClick={() => {
                setBaseline(formValues(rule));
                setReviewedRevision(rule.revision);
                setChanged(false);
                action.reset();
              }}
            >
              I reviewed the saved draft; keep my changes
            </Button>
          </FormSection>
        ) : null}
        <PanelBody>
          <ActionMessages
            error={action.error}
            notice={action.notice}
            className=""
          />
        </PanelBody>
        <PanelFooter>
          <Button
            type="submit"
            disabled={
              pending ||
              needsReview ||
              !selected ||
              categories.isError ||
              !fresh
            }
          >
            {pending ? "Saving…" : rule ? "Save draft" : "Create draft rule"}
          </Button>
        </PanelFooter>
      </form>
    </Panel>
  );
}

export function RetentionRuleEditor({
  creating = false,
}: {
  creating?: boolean;
}) {
  const { ruleId } = useParams<{ ruleId: string }>();
  const { canView, canManage } = useRetentionAccess();
  const router = useRouter();
  const client = useQueryClient();
  const rule = usePrivacyGovernanceGetRetentionRule(ruleId ?? "", {
    query: { enabled: !creating && canView, retry: false },
  });
  const activate = usePrivacyGovernanceActivateRetentionRule({
    mutation: { retry: false },
  });
  const retire = usePrivacyGovernanceRetireRetentionRule({
    mutation: { retry: false },
  });
  const action = usePrivacyAction();
  const [transition, setTransition] = useState<{
    kind: "activate" | "retire";
    revision: number;
  } | null>(null);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);
  const item = safeQueryData(rule)?.data;
  if (!canView || (creating && !canManage))
    return (
      <WorkspaceUnavailable title="Retention rule unavailable">
        This account cannot perform this retention action.
      </WorkspaceUnavailable>
    );
  if (!creating && rule.isPending)
    return <PrivacyDetailSkeleton label="Loading retention rule…" />;
  if (!creating && !item)
    return (
      <PrivacyQueryError
        error={rule.error}
        fallback="Retention rule could not be loaded."
        onRetry={() => void rule.refetch()}
      />
    );

  async function confirm() {
    if (!item || !transition || rule.isError || rule.isFetching || dirty)
      return;
    if (transition.revision !== item.revision) {
      setTransition(null);
      action.setNotice("The rule changed. Review its current terms again.");
      await rule.refetch();
      return;
    }
    const result = await action.run(
      () =>
        transition?.kind === "activate"
          ? activate.mutateAsync({
              ruleId: item.id,
              data: { expected_revision: transition.revision },
            })
          : retire.mutateAsync({
              ruleId: item.id,
              data: { expected_revision: transition.revision },
            }),
      "The rule could not be changed.",
      {
        onStepUpRequired: () => setTransition(null),
        onError: (caught) => {
          if (isRetentionConflict(caught)) {
            setTransition(null);
            action.setNotice(
              "The rule changed. Review its current state again.",
            );
            void rule.refetch();
          }
        },
      },
    );
    if (!result) return;
    setTransition(null);
    action.setNotice(
      transition?.kind === "activate"
        ? "Rule activated. Eligible records still require disposition approval."
        : "Rule retired. Pending cases require review under an active rule.",
    );
    await rule.refetch();
    await invalidateRetention(client);
  }

  return (
    <article className={pageSheetWidth}>
      <PrivacyPageHeader
        help={<RetentionHelp />}
        title={
          creating
            ? "Create retention draft"
            : (item?.label ?? "Retention rule")
        }
        backHref="/portal/privacy/retention/rules"
        backLabel="Retention rules"
        meta={
          item ? (
            <span>
              {item.code} · {item.status} · Revision {item.revision}
            </span>
          ) : undefined
        }
      />
      {rule.isError && item ? (
        <RefreshFailureNotice
          onRetry={() => void rule.refetch()}
          retrying={rule.isFetching}
        />
      ) : null}
      {saved ? (
        <p role="status" className="mb-4 text-sm text-success">
          Draft saved.
        </p>
      ) : null}
      {(creating || item?.status === "DRAFT") && canManage ? (
        <RuleForm
          rule={item}
          onDirty={setDirty}
          fresh={creating || (!rule.isError && !rule.isFetching)}
          onConflict={() => rule.refetch()}
          onSaved={(id) => {
            setSaved(true);
            void invalidateRetention(client);
            if (creating) router.push(`/portal/privacy/retention/rules/${id}`);
            else void rule.refetch();
          }}
        />
      ) : item ? (
        <Panel>
          <PanelHeader title="Rule terms" />
          <PanelBody>
            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted">Category / disposition</dt>
                <dd>
                  {categoryLabels[item.category]} ·{" "}
                  {dispositionActionLabel(item.action)} · {retentionContractLabel(item.contract_version)}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Duration</dt>
                <dd>
                  {item.duration_days} elapsed days after{" "}
                  {item.trigger === "SUBMITTED_AT"
                    ? "submission"
                    : "provider artifact readiness"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Policy reference</dt>
                <dd className="break-words">{item.policy_reference}</dd>
              </div>
              <div>
                <dt className="text-muted">Effective date</dt>
                <dd>{formatDateOnly(item.effective_on)}</dd>
              </div>
            </dl>
          </PanelBody>
        </Panel>
      ) : null}
      {item && canManage && item.status !== "RETIRED" ? (
        <Panel className="mt-5">
          <PanelHeader title="Rule actions" />
          <PanelBody>
            <p className="mb-3 text-sm">
              {item.status === "DRAFT"
                ? "Activation adopts these terms for eligibility. Every disposition still requires separate approval."
                : "Retirement stops pending disposition under this rule."}
            </p>
            <Button
              variant={item.status === "DRAFT" ? "primary" : "danger"}
              disabled={rule.isError || rule.isFetching || dirty}
              onClick={() => {
                action.reset();
                setTransition({
                  kind: item.status === "DRAFT" ? "activate" : "retire",
                  revision: item.revision,
                });
              }}
            >
              {item.status === "DRAFT" ? "Activate rule" : "Retire rule"}
            </Button>
          </PanelBody>
        </Panel>
      ) : null}
      {transition && transition.revision !== item?.revision ? (
        <Notice tone="warning" className="mt-4">
          The rule changed during review. Review its current terms and open
          confirmation again.
        </Notice>
      ) : null}
      <ActionMessages
        error={transition?.revision === item?.revision ? null : action.error}
        notice={action.notice}
      />
      <PrivacyConfirmDialog
        open={Boolean(transition) && transition?.revision === item?.revision}
        title={
          transition?.kind === "activate"
            ? "Activate this retention rule?"
            : "Retire this retention rule?"
        }
        description={
          <p>
            {transition?.kind === "activate"
              ? "Confirm that the duration and policy reference are institutionally approved. COMPASS will discover eligibility using these immutable terms. No record is disposed without a reviewed disposition approval."
              : "This rule will stop authorizing pending disposition. Queued cases will need a new review and approval under an active rule."}
          </p>
        }
        confirmLabel={
          transition?.kind === "activate" ? "Activate rule" : "Retire rule"
        }
        pendingLabel="Updating rule…"
        pending={activate.isPending || retire.isPending}
        confirmDisabled={
          rule.isError ||
          rule.isFetching ||
          dirty ||
          transition?.revision !== item?.revision
        }
        error={action.error}
        destructive={transition?.kind === "retire"}
        onOpenChange={(open) => {
          if (!open) setTransition(null);
        }}
        onConfirm={() => void confirm()}
      />
      {action.stepUpDialog}
    </article>
  );
}
