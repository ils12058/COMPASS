"use client";

import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import {
  exitInterviewCorrectionSections,
  exitInterviewCorrectionTargets,
  exitInterviewCorrectionTargetTitle,
  MAX_EXIT_INTERVIEW_CORRECTION_TARGETS,
  sortExitInterviewCorrectionTargets,
  type ExitInterviewCorrectionSectionId,
} from "@/features/exit-interviews/exit-interview-correction-targets";
import type { ExitInterviewCorrectionTarget } from "@/lib/api/generated/model";

type SectionChoices = {
  section: ExitInterviewCorrectionSectionId;
  title: string;
  whole?: ExitInterviewCorrectionTarget;
  groups: { label: string; targets: ExitInterviewCorrectionTarget[] }[];
};

// The record's allowed targets grouped the way the form is: section, then question group, in catalog
// order. A College Feedback category the record does not have never appears.
function sectionChoices(allowed: readonly ExitInterviewCorrectionTarget[]): SectionChoices[] {
  const sections = exitInterviewCorrectionSections.map<SectionChoices>(({ id, title }) => ({ section: id, title, groups: [] }));
  for (const code of allowed) {
    const definition = exitInterviewCorrectionTargets[code];
    const choices = sections.find((item) => item.section === definition.section);
    if (!choices) continue;
    if (definition.scope === "section") {
      choices.whole = code;
      continue;
    }
    const group = choices.groups.find((item) => item.label === definition.group);
    if (group) group.targets.push(code);
    else choices.groups.push({ label: definition.group, targets: [code] });
  }
  return sections.filter((choices) => choices.whole || choices.groups.length);
}

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

// The optional "Answers to review" part of the reopen dialog. It offers only the parts of this
// record's saved form, so a current UCN F9 response never offers Program Chair items, while a legacy
// response keeps them. The written reason stays required, and the backend checks the selection again.
export function ExitInterviewCorrectionTargetChooser({
  allowed,
  value,
  onChange,
  disabled = false,
}: {
  allowed: readonly ExitInterviewCorrectionTarget[];
  value: readonly ExitInterviewCorrectionTarget[];
  onChange: (value: ExitInterviewCorrectionTarget[]) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const [openSection, setOpenSection] = useState<ExitInterviewCorrectionSectionId | null>(null);
  const selected = new Set(value);
  const atLimit = value.length >= MAX_EXIT_INTERVIEW_CORRECTION_TARGETS;
  const focusAfterRemove = useRef<number | null>(null);
  const selectedHeading = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const index = focusAfterRemove.current;
    if (index === null) return;
    focusAfterRemove.current = null;
    const next = document.getElementById(`${id}-remove-${Math.min(index, value.length - 1)}`);
    (next ?? selectedHeading.current)?.focus();
  }, [id, value]);

  function toggle(code: ExitInterviewCorrectionTarget, checked: boolean) {
    if (checked && (selected.has(code) || atLimit || !allowed.includes(code))) return;
    onChange(sortExitInterviewCorrectionTargets(checked ? [...value, code] : value.filter((item) => item !== code)));
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
        {sectionChoices(allowed).map(({ section, title, whole, groups }) => {
          const count = [...(whole ? [whole] : []), ...groups.flatMap((group) => group.targets)].filter((code) => selected.has(code)).length;
          return (
            <Disclosure
              key={section}
              open={openSection === section}
              onOpenChange={(open) => setOpenSection(open ? section : (current) => (current === section ? null : current))}
              summary={
                <span>
                  {title}
                  {count ? <span className="ml-2 font-normal text-muted">{count} selected</span> : null}
                </span>
              }
              summaryClassName="w-full px-3"
              contentClassName="space-y-3 border-t border-border px-3 pb-3 pt-2"
            >
              {whole ? (
                <TargetCheckbox
                  label="Whole section"
                  description={`Asks the Student to look at every answer in ${title}.`}
                  checked={selected.has(whole)}
                  disabled={!selected.has(whole) && atLimit}
                  onChange={(checked) => toggle(whole, checked)}
                />
              ) : null}
              {groups.map((group) => (
                <fieldset key={group.label} className="min-w-0">
                  <legend className="text-xs font-semibold text-muted">{group.label}</legend>
                  <div className="mt-1">
                    {group.targets.map((code) => (
                      <TargetCheckbox
                        key={code}
                        label={exitInterviewCorrectionTargets[code].label}
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
          ? `${value.length} of ${MAX_EXIT_INTERVIEW_CORRECTION_TARGETS} selected. Remove one to choose another.`
          : `${value.length} of ${MAX_EXIT_INTERVIEW_CORRECTION_TARGETS} selected`}
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
              const title = exitInterviewCorrectionTargetTitle(code);
              return (
                <li key={code} className="flex items-center justify-between gap-3 py-1 pl-3 pr-1 text-sm leading-5 text-ink">
                  <span className="min-w-0 break-words">{title}</span>
                  <Button id={`${id}-remove-${index}`} variant="quiet" aria-label={`Remove ${title}`} onClick={() => remove(index)}>
                    Remove
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mt-1 text-sm leading-6 text-muted">None. The Student will see only your reason.</p>
        )}
      </div>
    </fieldset>
  );
}
