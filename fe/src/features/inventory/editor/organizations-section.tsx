"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { SelectField, TextField } from "@/features/inventory/editor/fields";
import { InventoryReviewHintText, useInventoryReviewLookup } from "@/features/inventory/editor/inventory-review-context";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import { organizationTextLimits, transportationTextLimits } from "@/features/inventory/inventory-field-limits";
import { organizationScopeOptions, transportationFrequencyOptions, transportationModes } from "@/features/inventory/inventory-presentation";
import { FieldGroup } from "@/features/inventory/inventory-shared";
import {
  OrganizationScopeValue,
  TransportationFrequencyCategoryValue,
  type OrganizationMembershipPayload,
  type TransportationEntryPayload,
} from "@/lib/api/generated/model";

const emptyOrganizationMemberships: OrganizationMembershipPayload[] = [];

function rowsForScope(
  rows: OrganizationMembershipPayload[],
  scope: OrganizationScopeValue,
): OrganizationMembershipPayload[] {
  return rows.filter((row) => row.scope === scope);
}

export function OrganizationsSection({ draft, onChange, validationIssues = [] }: InventorySectionProps) {
  const errorFor = (targetId: string) =>
    validationIssues.find((issue) => issue.targetId === targetId)?.message;
  const memberships = draft.organization_memberships ?? emptyOrganizationMemberships;
  const transportation = draft.transportation_entries ?? [];
  // Memberships are reviewed as whole lists: rows have no identity that survives a save or a move.
  const review = useInventoryReviewLookup();
  const modesReview = review("inventory-transport-modes");
  const focusAfterUpdate = useRef<string | null>(null);

  useEffect(() => {
    const target = focusAfterUpdate.current;
    if (!target) return;
    document.getElementById(target)?.focus();
    focusAfterUpdate.current = null;
  }, [memberships]);

  function replaceScopeRows(scope: OrganizationScopeValue, rows: OrganizationMembershipPayload[]) {
    const otherRows = memberships.filter((row) => row.scope !== scope);
    onChange({
      organization_memberships: [
        ...otherRows,
        ...rows.map((row, index) => ({ ...row, scope, sort_order: index })),
      ],
    });
  }

  function updateTransport(mode: TransportationEntryPayload["mode"], patch: Partial<TransportationEntryPayload>) {
    const existing = transportation.find((entry) => entry.mode === mode);
    const rest = transportation.filter((entry) => entry.mode !== mode);
    onChange({ transportation_entries: [...rest, { mode, ...existing, ...patch }] });
  }

  function toggleTransport(mode: TransportationEntryPayload["mode"], checked: boolean) {
    const next = checked
      ? transportation.some((entry) => entry.mode === mode)
        ? transportation
        : [...transportation, { mode }]
      : transportation.filter((entry) => entry.mode !== mode);
    onChange({ transportation_entries: next });
  }

  return (
    <div className="space-y-7">
      <FieldGroup legend="Membership in organizations">
        <div className="space-y-7">
          {organizationScopeOptions.map(([scope, label]) => {
            const rows = rowsForScope(memberships, scope);
            const listReview = review(`inventory-membership-${scope.toLowerCase()}`);
            return (
              <section key={scope} aria-labelledby={`inventory-membership-${scope.toLowerCase()}`} aria-describedby={listReview.hint?.id}>
                <h3 id={`inventory-membership-${scope.toLowerCase()}`} className="font-semibold text-ink">{label}</h3>
                <InventoryReviewHintText hint={listReview.hint} className="mt-1" />
                <div className="mt-3 divide-y divide-border rounded-sm border border-border">
                  {rows.map((row, index) => (
                    <div key={`${scope}-${index}`} className="grid gap-4 px-4 py-4 @md/inventory:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] @md/inventory:items-end">
                      <TextField
                        id={`inventory-membership-${scope.toLowerCase()}-${index}-organization`}
                        label="Organization name"
                        maxLength={organizationTextLimits.organization_name}
                        value={row.organization_name}
                        onChange={(value) => replaceScopeRows(scope, rows.map((item, itemIndex) => itemIndex === index ? { ...item, organization_name: value } : item))}
                      />
                      <TextField
                        id={`inventory-membership-${scope.toLowerCase()}-${index}-position`}
                        label="Position or title"
                        maxLength={organizationTextLimits.position_title}
                        value={row.position_title}
                        onChange={(value) => replaceScopeRows(scope, rows.map((item, itemIndex) => itemIndex === index ? { ...item, position_title: value } : item))}
                      />
                      <Button
                        variant="quiet"
                        aria-label={`Remove ${label.toLowerCase()} organization ${index + 1}`}
                        onClick={() => {
                          const nextRows = rows.filter((_, itemIndex) => itemIndex !== index);
                          const nextFocusIndex = Math.min(index, nextRows.length - 1);
                          focusAfterUpdate.current = nextFocusIndex >= 0
                            ? `inventory-membership-${scope.toLowerCase()}-${nextFocusIndex}-organization`
                            : `inventory-membership-${scope.toLowerCase()}-add`;
                          replaceScopeRows(scope, nextRows);
                        }}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
                <Button
                  id={`inventory-membership-${scope.toLowerCase()}-add`}
                  variant="secondary"
                  className="mt-3"
                  aria-describedby={review(`inventory-membership-${scope.toLowerCase()}-add`).describedBy}
                  onClick={() => {
                    focusAfterUpdate.current = `inventory-membership-${scope.toLowerCase()}-${rows.length}-organization`;
                    replaceScopeRows(scope, [...rows, { scope, sort_order: rows.length }]);
                  }}
                >
                  Add organization
                </Button>
              </section>
            );
          })}
        </div>
      </FieldGroup>

      <FieldGroup legend="Transportation">
        <p className="mb-4 text-sm leading-6 text-muted">
          Select only the ways you use to travel to and from the university. Each selected mode has its own optional frequency and fare details.
        </p>
        <div
          id="inventory-transport-modes"
          role="group"
          aria-label="Transportation modes"
          aria-describedby={modesReview.describedBy}
          className="grid gap-x-5 gap-y-3 @md/inventory:grid-cols-2 @2xl/inventory:grid-cols-3"
        >
          {transportationModes.map(([mode, label]) => {
            const selected = transportation.some((entry) => entry.mode === mode);
            return (
              <label key={mode} className="flex min-h-9 items-center gap-3 text-sm font-medium text-ink">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-brand"
                  checked={selected}
                  onChange={(event) => toggleTransport(mode, event.target.checked)}
                />
                {label}
              </label>
            );
          })}
        </div>
        <InventoryReviewHintText hint={modesReview.hint} />
        <div className="mt-5 divide-y divide-border rounded-sm border border-border">
          {transportationModes.flatMap(([mode, label]) => {
            const entry = transportation.find((item) => item.mode === mode);
            if (!entry) return [];
            const rowReview = review(`inventory-transport-${mode.toLowerCase()}`);
            return [
              <section key={mode} className="grid gap-4 px-4 py-5 @md/inventory:grid-cols-2" aria-labelledby={`inventory-transport-${mode.toLowerCase()}`} aria-describedby={rowReview.hint?.id}>
                <div className="@md/inventory:col-span-2">
                  <h3 id={`inventory-transport-${mode.toLowerCase()}`} className="font-semibold text-ink">{label}</h3>
                  <InventoryReviewHintText hint={rowReview.hint} className="mt-1" />
                </div>
                <SelectField
                  id={`inventory-transport-${mode.toLowerCase()}-frequency-category`}
                  label="Frequency"
                  error={errorFor(`inventory-transport-${mode.toLowerCase()}-frequency-category`)}
                  value={entry.frequency_category}
                  options={transportationFrequencyOptions}
                  onChange={(value) => updateTransport(mode, {
                    frequency_category: value,
                    ...(value === TransportationFrequencyCategoryValue.OTHER
                      ? {}
                      : { frequency: "" }),
                  })}
                />
                {entry.frequency_category === TransportationFrequencyCategoryValue.OTHER ? (
                  <TextField
                    id={`inventory-transport-${mode.toLowerCase()}-frequency-other`}
                    label="Other frequency"
                    maxLength={transportationTextLimits.frequency}
                    error={errorFor(`inventory-transport-${mode.toLowerCase()}-frequency-other`)}
                    value={entry.frequency}
                    onChange={(value) => updateTransport(mode, { frequency: value })}
                    hint="Choosing a different frequency clears this detail."
                    required
                  />
                ) : null}
                <TextField
                  id={`inventory-transport-${mode.toLowerCase()}-fare`}
                  label="Fare (optional)"
                  type="number"
                  min={0}
                  step={0.01}
                  value={entry.fare}
                  onChange={(value) => updateTransport(mode, { fare: value || null })}
                  hint="In pesos (₱)."
                  error={errorFor(`inventory-transport-${mode.toLowerCase()}-fare`)}
                />
              </section>,
            ];
          })}
        </div>
      </FieldGroup>
    </div>
  );
}
