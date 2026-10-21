"use client";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";

// Presentation only. The form owns section order, validation, persistence and focus destinations.
export function FormSectionNavigation<Id extends string>({
  id,
  label,
  navigationLabel,
  sections,
  current,
  onSelect,
}: {
  id: string;
  label: string;
  navigationLabel: string;
  sections: readonly { id: Id; label: string; attentionCount?: number }[];
  current: Id;
  // Keep focus on the native mobile selector; other navigation can focus the section heading.
  onSelect: (id: Id, focusSection: boolean) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-sm font-semibold text-ink md:sr-only">
        {label}
      </label>
      <Select id={id} className="min-h-11 md:hidden" value={current} onChange={(event) => {
        const next = sections.find((section) => section.id === event.target.value);
        if (next) onSelect(next.id, false);
      }}>
        {sections.map((section) => (
          <option key={section.id} value={section.id}>
            {section.label}{section.attentionCount ? ` · ${section.attentionCount} needs attention` : ""}
          </option>
        ))}
      </Select>
      <nav aria-label={navigationLabel} className="hidden md:block">
        <ol className="space-y-1">
          {sections.map((section, index) => (
            <li key={section.id}>
              <button
                type="button"
                aria-current={current === section.id ? "step" : undefined}
                className={`flex min-h-11 w-full items-start gap-2 rounded-md px-3 py-2 text-left text-sm leading-6 transition-colors motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${current === section.id ? "bg-brand-wash font-semibold text-brand" : "text-muted hover:bg-surface-subtle hover:text-ink"}`}
                onClick={() => onSelect(section.id, true)}
              >
                <span aria-hidden="true" className="w-4 shrink-0">{index + 1}.</span>
                <span className="min-w-0 flex-1">{section.label}</span>
                {section.attentionCount ? <span className="shrink-0 font-semibold text-warning">{section.attentionCount}<span className="sr-only"> answers need attention</span></span> : null}
              </button>
            </li>
          ))}
        </ol>
      </nav>
    </div>
  );
}

// Keep a single polite live region mounted. A successful save message must come from the owner
// only after its persistence operation confirms success. A failure must never clear dirty state.
export function FormSaveStatus({ dirty, saving, savedMessage }: {
  dirty: boolean;
  saving: boolean;
  savedMessage?: string | null;
}) {
  return (
    <p role="status" aria-atomic="true" className={`text-sm ${dirty && !saving ? "font-medium text-warning" : "text-muted"}`}>
      {saving ? "Saving…" : dirty ? "Unsaved changes" : savedMessage || "Saved draft"}
    </p>
  );
}

// The domain supplies errors and handles navigation to the original owning field, including
// conditional/section targets. This component neither validates answers nor collects form data.
export function FormErrorSummary<Issue extends { message: string }>({
  id, issues, onSelect, title = "Complete these answers", instruction = "Select an item below to go to the question.",
}: {
  id: string;
  issues: readonly Issue[];
  title?: string;
  instruction?: string;
  onSelect: (issue: Issue) => void;
}) {
  if (!issues.length) return null;
  return (
    <section aria-labelledby={id}>
      <h3 id={id} className="font-semibold text-ink">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-muted">{instruction}</p>
      <ul className="mt-2 space-y-1">
        {issues.map((issue, index) => (
          <li key={index}>
            <Button variant="quiet" className="min-h-11 justify-start whitespace-normal px-0 text-left" onClick={() => onSelect(issue)}>
              {issue.message}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}

// Continuous forms keep all sections mounted. Anchors expose their destinations while the owning
// form handles explicit scroll/focus; no step state, completion model or scroll observer is needed.
export function FormSectionLinks({ id, label, sections, onSelect }: {
  id?: string;
  label: string;
  sections: readonly { id: string; label: string }[];
  onSelect: (id: string) => void;
}) {
  return (
    <nav id={id} tabIndex={id ? -1 : undefined} aria-label={label} className="min-w-0 scroll-mt-24 [overflow-wrap:anywhere] focus:outline-none focus-visible:ring-2 focus-visible:ring-focus">
      <p className="text-sm font-semibold text-ink">On this page</p>
      <ul className="mt-1 grid grid-cols-2 gap-x-4 sm:flex sm:flex-wrap sm:gap-x-5">
        {sections.map((section) => (
          <li key={section.id} className="min-w-0">
            <a href={`#${section.id}`} className="inline-flex min-h-11 items-center rounded-sm text-sm font-medium leading-5 text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" onClick={(event) => {
              event.preventDefault();
              onSelect(section.id);
            }}>{section.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
