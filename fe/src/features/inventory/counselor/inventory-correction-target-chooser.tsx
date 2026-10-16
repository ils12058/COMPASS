"use client";

import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import {
  inventoryCorrectionTargetLabel,
  inventoryCorrectionTargetOrder,
  inventoryCorrectionTargets,
  inventorySectionLabel,
  MAX_INVENTORY_CORRECTION_TARGETS,
  sortInventoryCorrectionTargets,
  type InventoryEditorSectionId,
} from "@/features/inventory/inventory-correction-targets";
import type { InventoryCorrectionTarget } from "@/lib/api/generated/model";

type SectionChoices = {
  section: InventoryEditorSectionId;
  whole: InventoryCorrectionTarget;
  groups: { label: string; targets: InventoryCorrectionTarget[] }[];
};

// The catalog grouped the way the Student's editor is: section, then field group, in catalog order.
const sectionChoices: SectionChoices[] = (() => {
  const sections = new Map<InventoryEditorSectionId, SectionChoices>();
  for (const code of inventoryCorrectionTargetOrder) {
    const definition = inventoryCorrectionTargets[code];
    if (definition.scope === "section") {
      sections.set(definition.section, { section: definition.section, whole: code, groups: [] });
      continue;
    }
    const choices = sections.get(definition.section);
    if (!choices) continue;
    const group = choices.groups.find((item) => item.label === definition.group);
    if (group) group.targets.push(code);
    else choices.groups.push({ label: definition.group, targets: [code] });
  }
  return [...sections.values()];
})();

function TargetCheckbox({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex min-h-9 items-start gap-2.5 py-1 text-sm leading-5 text-ink">
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 shrink-0 accent-brand"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        {label}
        {description ? <span className="block text-xs text-muted">{description}</span> : null}
      </span>
    </label>
  );
}

// The optional "Answers to review" part of the reopen dialog. It only names parts of the form for the
// Student to look at again; the written instructions stay required, and the backend validates the
// selection. One section is open at a time, so the dialog never lists all 148 choices at once.
export function InventoryCorrectionTargetChooser({
  value,
  onChange,
  disabled = false,
}: {
  value: readonly InventoryCorrectionTarget[];
  onChange: (value: InventoryCorrectionTarget[]) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const [openSection, setOpenSection] = useState<InventoryEditorSectionId | null>(null);
  const selected = new Set(value);
  const atLimit = value.length >= MAX_INVENTORY_CORRECTION_TARGETS;
  // After a Remove button disappears, focus moves to the next one, or to the list heading.
  const focusAfterRemove = useRef<number | null>(null);
  const selectedHeading = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const index = focusAfterRemove.current;
    if (index === null) return;
    focusAfterRemove.current = null;
    const next = document.getElementById(`${id}-remove-${Math.min(index, value.length - 1)}`);
    (next ?? selectedHeading.current)?.focus();
  }, [id, value]);

  function toggle(code: InventoryCorrectionTarget, checked: boolean) {
    if (checked && (selected.has(code) || atLimit)) return;
    onChange(sortInventoryCorrectionTargets(checked ? [...value, code] : value.filter((item) => item !== code)));
  }

  function remove(index: number) {
    focusAfterRemove.current = index;
    onChange(value.filter((_, itemIndex) => itemIndex !== index));
  }

  return (
    <fieldset disabled={disabled} aria-describedby={`${id}-help ${id}-count`} className="min-w-0">
      <legend className="text-sm font-semibold text-ink">Answers to review (optional)</legend>
      <p id={`${id}-help`} className="mt-1 text-xs leading-5 text-muted">
        Choose the parts of the form the Student should look at again. They will see these with your instructions.
      </p>

      <div className="mt-3 divide-y divide-border rounded-sm border border-border">
        {sectionChoices.map(({ section, whole, groups }) => {
          const label = inventorySectionLabel(section);
          const count = [whole, ...groups.flatMap((group) => group.targets)].filter((code) => selected.has(code)).length;
          return (
            <Disclosure
              key={section}
              open={openSection === section}
              onOpenChange={(open) => setOpenSection(open ? section : (current) => (current === section ? null : current))}
              summary={
                <span>
                  {label}
                  {count ? <span className="ml-2 font-normal text-muted">{count} selected</span> : null}
                </span>
              }
              summaryClassName="w-full px-3"
              contentClassName="space-y-3 border-t border-border px-3 pb-3 pt-2"
            >
              <TargetCheckbox
                label="Whole section"
                description={`Asks the Student to look at every answer in ${label}.`}
                checked={selected.has(whole)}
                disabled={!selected.has(whole) && atLimit}
                onChange={(checked) => toggle(whole, checked)}
              />
              {groups.map((group) => (
                <fieldset key={group.label} className="min-w-0">
                  <legend className="text-xs font-semibold text-muted">{group.label}</legend>
                  <div className="mt-1">
                    {group.targets.map((code) => (
                      <TargetCheckbox
                        key={code}
                        label={inventoryCorrectionTargets[code].label}
                        checked={selected.has(code)}
                        disabled={!selected.has(code) && atLimit}
                        onChange={(checked) => toggle(code, checked)}
                      />
                    ))}
                  </div>
                </fieldset>
              ))}
            </Disclosure>
          );
        })}
      </div>

      <p id={`${id}-count`} aria-live="polite" className="mt-2 text-xs leading-5 text-muted">
        {atLimit
          ? `${value.length} of ${MAX_INVENTORY_CORRECTION_TARGETS} selected. Remove one to choose another.`
          : `${value.length} of ${MAX_INVENTORY_CORRECTION_TARGETS} selected`}
      </p>

      <div className="mt-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p ref={selectedHeading} id={`${id}-selected`} tabIndex={-1} className="text-sm font-semibold text-ink focus:outline-none">
            Selected for review
          </p>
          {value.length ? (
            <Button
              variant="quiet"
              onClick={() => {
                focusAfterRemove.current = 0;
                onChange([]);
              }}
            >
              Clear selection
            </Button>
          ) : null}
        </div>
        {value.length ? (
          <ul aria-labelledby={`${id}-selected`} className="mt-2 divide-y divide-border rounded-sm border border-border">
            {value.map((code, index) => {
              const label = inventoryCorrectionTargetLabel(code);
              return (
                <li key={code} className="flex items-center justify-between gap-3 py-1 pl-3 pr-1 text-sm leading-5 text-ink">
                  <span className="min-w-0 break-words">{label}</span>
                  <Button id={`${id}-remove-${index}`} variant="quiet" aria-label={`Remove ${label}`} onClick={() => remove(index)}>
                    Remove
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mt-1 text-sm leading-6 text-muted">None. The Student will see only your instructions.</p>
        )}
      </div>
    </fieldset>
  );
}
