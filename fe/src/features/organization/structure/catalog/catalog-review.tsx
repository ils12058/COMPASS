import type { CatalogImpactResponse } from "@/lib/api/generated/model";
import { CatalogImpact, cascadeLabel } from "./catalog-impact";
import { classificationLabel, levelsLabel, parentLabel, type CatalogCommand, type CatalogTarget } from "./catalog-model";

export function CatalogReview({ command, impact, parent, cascade = false, onCascade, disabled = false }: { command: CatalogCommand; parent?: CatalogTarget; impact?: CatalogImpactResponse; cascade?: boolean; onCascade?: (value: boolean) => void; disabled?: boolean }) {
  const target = "target" in command ? command.target : undefined;
  const data = command.data;
  return <>
    {command.operation === "rename" ? <>
      <p>Current name: {command.target.record.name}</p>
      <p>New name: <strong>{command.data.name}</strong></p>
      <p>Current linked labels may change. Saved historical facts remain; finalized documents are not regenerated.</p>
    </> : <p className="break-words font-semibold">{target?.record.name ?? ("name" in data ? data.name : "")} · {target?.record.code ?? ("code" in data ? data.code : "")}</p>}
    {command.operation === "policy" ? <div><p className="font-semibold">Current Program settings</p><p>{classificationLabel(command.target.record.academic_classification)} · {levelsLabel(command.target.record.applicable_year_levels, command.target.record.year_level_policy_status)}</p></div> : null}
    {command.operation === "policy" || command.operation === "createProgram" ? <div><p className="font-semibold">Proposed Program settings</p><p>{classificationLabel(command.data.academic_classification)} · {levelsLabel(command.data.applicable_year_levels, command.data.year_level_policy_status)}</p><p>These settings change the academic requirements for new work. Submitted Individual Inventories and issued certificates stay as they are.</p></div> : null}
    {command.operation === "status" ? <>
      <p>Status: {command.target.record.is_active ? "Active" : "Retired"} → <strong>{command.data.is_active ? "Active" : "Retired"}</strong></p>
      {command.data.is_active ? <p>Any parent campus or college must be active, and programs need complete settings. Linked colleges and programs aren&apos;t reactivated automatically.</p> : impact ? <>
        <CatalogImpact impact={impact} kind={command.target.kind} />
        {impact.active_children.length ? <label className="flex min-h-11 items-start gap-3 py-2">
          <input type="checkbox" disabled={disabled} className="mt-1 size-4 shrink-0 accent-brand" checked={cascade} onChange={(event) => onCascade?.(event.target.checked)} />
          <span>{cascadeLabel(impact)}. All selected records retire together.</span>
        </label> : null}
      </> : null}
    </> : null}
    {target ? <p>{command.operation === "rename" ? `Code: ${target.record.code} · ` : ""}{parentLabel(target)}</p> : <p>Initial status: {"is_active" in data && data.is_active ? "Active" : "Retired"}</p>}
    {parent ? <p>Parent: {parent.record.name} ({parent.record.code}) · {parentLabel(parent)}</p> : null}
    <p className="break-words">Change note: {data.basis}</p>
  </>;
}
