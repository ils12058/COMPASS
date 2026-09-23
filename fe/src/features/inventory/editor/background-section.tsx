"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { SelectField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import { sexOptions } from "@/features/inventory/inventory-presentation";
import { FieldGroup } from "@/features/inventory/inventory-shared";
import type { SiblingPayload } from "@/lib/api/generated/model";

const emptySiblings: SiblingPayload[] = [];

export function BackgroundSection({ draft, onChange }: InventorySectionProps) {
  const siblings = draft.siblings ?? emptySiblings;
  const focusAfterUpdate = useRef<string | null>(null);

  useEffect(() => {
    const target = focusAfterUpdate.current;
    if (!target) return;
    document.getElementById(target)?.focus();
    focusAfterUpdate.current = null;
  }, [siblings]);

  function setRows(rows: SiblingPayload[]) {
    onChange({ siblings: rows.map((row, index) => ({ ...row, sort_order: index })) });
  }

  function updateRow(index: number, patch: Partial<SiblingPayload>) {
    setRows(siblings.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row));
  }

  function moveRow(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= siblings.length) return;
    const rows = [...siblings];
    [rows[index], rows[target]] = [rows[target], rows[index]];
    setRows(rows);
  }

  return (
    <div className="space-y-7">
      <FieldGroup legend="Siblings">
        <p className="mb-5 text-sm leading-6 text-muted">
          List siblings from eldest to youngest, including yourself. Mark the row that represents you.
        </p>
        <ol className="divide-y divide-border border-y border-border">
          {siblings.map((sibling, index) => (
            <li key={`sibling-${index}`} className="py-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-semibold text-ink">Sibling {index + 1}</h3>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    disabled={index === 0}
                    aria-label={`Move sibling ${index + 1} up`}
                    onClick={() => moveRow(index, -1)}
                  >
                    Move up
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={index === siblings.length - 1}
                    aria-label={`Move sibling ${index + 1} down`}
                    onClick={() => moveRow(index, 1)}
                  >
                    Move down
                  </Button>
                  <Button
                    variant="quiet"
                    aria-label={`Remove sibling ${index + 1}`}
                    onClick={() => {
                      const nextRows = siblings.filter((_, rowIndex) => rowIndex !== index);
                      const nextFocusIndex = Math.min(index, nextRows.length - 1);
                      focusAfterUpdate.current = nextFocusIndex >= 0
                        ? `inventory-sibling-${nextFocusIndex}-name`
                        : "inventory-sibling-add";
                      setRows(nextRows);
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <TextField
                  id={`inventory-sibling-${index}-name`}
                  label="Name"
                  value={sibling.name}
                  onChange={(value) => updateRow(index, { name: value })}
                />
                <SelectField
                  id={`inventory-sibling-${index}-sex`}
                  label="Sex"
                  value={sibling.sex}
                  options={sexOptions}
                  onChange={(value) => updateRow(index, { sex: value })}
                />
                <TextField
                  id={`inventory-sibling-${index}-age`}
                  label="Age"
                  type="number"
                  value={sibling.age}
                  onChange={(value) => updateRow(index, { age: value ? Number(value) : null })}
                />
                <TextField
                  id={`inventory-sibling-${index}-education`}
                  label="Educational attainment"
                  value={sibling.educational_attainment}
                  onChange={(value) => updateRow(index, { educational_attainment: value })}
                />
                <TextField
                  id={`inventory-sibling-${index}-occupation`}
                  label="Occupation"
                  value={sibling.occupation}
                  onChange={(value) => updateRow(index, { occupation: value })}
                />
                <label className="flex min-h-10 items-center gap-3 text-sm font-medium text-ink">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-brand"
                    checked={sibling.is_self ?? false}
                    onChange={(event) => {
                      setRows(
                        siblings.map((row, rowIndex) => ({
                          ...row,
                          is_self: rowIndex === index ? event.target.checked : event.target.checked ? false : row.is_self,
                        })),
                      );
                    }}
                  />
                  This is me
                </label>
              </div>
            </li>
          ))}
        </ol>
        <Button
          id="inventory-sibling-add"
          variant="secondary"
          className="mt-4"
          onClick={() => {
            focusAfterUpdate.current = `inventory-sibling-${siblings.length}-name`;
            setRows([...siblings, { sort_order: siblings.length }]);
          }}
        >
          Add sibling
        </Button>
      </FieldGroup>

      <FieldGroup legend="Personal background and unique features">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextAreaField
            id="inventory-friends-in-school"
            label="Friends in school"
            value={draft.friends_in_school}
            onChange={(value) => onChange({ friends_in_school: value })}
          />
          <TextAreaField
            id="inventory-friends-outside-school"
            label="Friends outside school"
            value={draft.friends_outside_school}
            onChange={(value) => onChange({ friends_outside_school: value })}
          />
          <TextAreaField
            id="inventory-special-interest"
            label="Special interest"
            value={draft.special_interest}
            onChange={(value) => onChange({ special_interest: value })}
          />
          <TextAreaField
            id="inventory-special-skills"
            label="Special skills and talents"
            value={draft.special_skills_talents}
            onChange={(value) => onChange({ special_skills_talents: value })}
          />
          <TextAreaField
            id="inventory-hobbies"
            label="Hobbies and recreation activities"
            value={draft.hobbies_recreation}
            onChange={(value) => onChange({ hobbies_recreation: value })}
          />
          <TextAreaField
            id="inventory-ambition"
            label="Ambition or goal"
            value={draft.ambition_goal}
            onChange={(value) => onChange({ ambition_goal: value })}
          />
          <TextAreaField
            id="inventory-characteristics"
            label="Characteristics that describe you best"
            value={draft.characteristics}
            onChange={(value) => onChange({ characteristics: value })}
          />
        </div>
      </FieldGroup>
    </div>
  );
}
