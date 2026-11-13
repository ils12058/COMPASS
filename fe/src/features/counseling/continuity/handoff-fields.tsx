import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CaseHandoffSections } from "@/lib/api/generated/model";

export const emptyHandoff: CaseHandoffSections = {
  context_and_purpose: "", support_and_progress: "",
  continuing_considerations: "", receiver_next_steps: "",
};
export const handoffSectionLabels: Record<keyof CaseHandoffSections, string> = {
  context_and_purpose: "Current concern and handoff purpose",
  support_and_progress: "Support provided and progress",
  continuing_considerations: "Considerations for continuing support",
  receiver_next_steps: "What the receiver should review or do next",
};
export function handoffLength(sections: CaseHandoffSections) {
  return Object.values(sections).reduce((total, text) => total + text.length, 0);
}
export function HandoffFields({ value, onChange, disabled = false }: {
  value: CaseHandoffSections; onChange: (value: CaseHandoffSections) => void; disabled?: boolean;
}) {
  const length = handoffLength(value);
  return <div className="space-y-4">
    {(Object.keys(handoffSectionLabels) as (keyof CaseHandoffSections)[]).map(key => <div className="grid gap-1" key={key}>
      <Label htmlFor={`case-handoff-${key}`}>{handoffSectionLabels[key]}</Label>
      <Textarea id={`case-handoff-${key}`} rows={4} value={value[key]} disabled={disabled}
        aria-invalid={length > 12000} aria-describedby="case-handoff-length"
        onChange={event => onChange({ ...value, [key]: event.target.value })} />
    </div>)}
    <p id="case-handoff-length" className={`text-sm ${length > 12000 ? "text-danger" : "text-muted"}`}>
      {length.toLocaleString()} / 12,000 narrative characters across all sections
    </p>
  </div>;
}
