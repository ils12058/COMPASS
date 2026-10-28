import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { AcademicClassification, YearLevelPolicyStatus } from "@/lib/api/generated/model";
import { yearLevelLabel } from "@/lib/year-level";
import { classificationLabel, type CatalogDraft } from "./catalog-model";

export function CatalogPolicyFields({ draft, onChange, disabled }: { draft: CatalogDraft; onChange: (draft: CatalogDraft) => void; disabled: boolean }) {
  return <fieldset className="space-y-4" disabled={disabled}>
    <legend className="mb-3 font-semibold">Program settings</legend>
    <div className="grid gap-2">
      <Label htmlFor="catalog-classification">Classification</Label>
      <Select id="catalog-classification" value={draft.classification ?? ""} onChange={(event) => {
        const value = Object.values(AcademicClassification).find((value) => value === event.target.value) ?? null;
        onChange({ ...draft, classification: value });
      }}>
        <option value="">Not set yet</option>
        {Object.values(AcademicClassification).map((value) => <option key={value} value={value}>{classificationLabel(value)}</option>)}
      </Select>
    </div>
    <div className="grid gap-2">
      <Label htmlFor="catalog-policy-status">Year levels</Label>
      <Select id="catalog-policy-status" value={draft.policyStatus} onChange={(event) => {
        const status = Object.values(YearLevelPolicyStatus).find((value) => value === event.target.value);
        if (status) onChange({ ...draft, policyStatus: status });
      }}>
        <option value={YearLevelPolicyStatus.PENDING_POLICY}>Not set yet</option>
        <option value={YearLevelPolicyStatus.CONFIGURED}>Set year levels</option>
      </Select>
    </div>
    {draft.policyStatus === "CONFIGURED" ? <fieldset aria-describedby="catalog-levels-help">
      <legend className="font-semibold text-sm">Select year levels</legend>
      <p id="catalog-levels-help" className="mt-1 text-sm text-muted">Select each approved level. Gaps are retained.</p>
      <div className="mt-2 grid grid-cols-2 gap-1 sm:grid-cols-3">
        {Array.from({ length: 10 }, (_, index) => index + 1).map((level) => <label key={level} className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" className="size-4 accent-brand" checked={draft.levels.includes(level)} onChange={(event) => onChange({ ...draft, levels: event.target.checked ? [...draft.levels, level].sort((a,b) => a-b) : draft.levels.filter((value) => value !== level) })} />
          {yearLevelLabel(level)}
        </label>)}
      </div>
    </fieldset> : <p className="text-sm text-muted">Year levels are not set yet. An incomplete Program can be saved as inactive; activation requires a classification and year levels.</p>}
  </fieldset>;
}
