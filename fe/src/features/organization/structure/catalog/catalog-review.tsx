import type { CatalogImpactResponse } from "@/lib/api/generated/model";
import { impactExplanations, preservedCategoryLabel } from "./catalog-impact";
import { classificationLabel, levelsLabel, parentLabel, type CatalogCommand, type CatalogTarget } from "./catalog-model";

export function CatalogReview({ command, impact, parent }: { command: CatalogCommand; parent?: CatalogTarget; impact?: CatalogImpactResponse }) {
  const target = "target" in command ? command.target : undefined;
  const data = command.data;
  return <>
    {command.operation === "rename" ? <>
      <p>Current name: {command.target.record.name}</p>
      <p>New name: <strong>{command.data.name}</strong></p>
      <p>Current linked labels may change. Saved historical facts remain; finalized documents are not regenerated.</p>
    </> : <p className="break-words font-semibold">{target?.record.name ?? ("name" in data ? data.name : "")} · {target?.record.code ?? ("code" in data ? data.code : "")}</p>}
    {command.operation === "policy" ? <div><p className="font-semibold">Current Program settings</p><p>{classificationLabel(command.target.record.academic_classification)} · {levelsLabel(command.target.record.applicable_year_levels, command.target.record.year_level_policy_status)}</p></div> : null}
    {command.operation === "policy" || command.operation === "createProgram" ? <div><p className="font-semibold">Proposed Program settings</p><p>{classificationLabel(command.data.academic_classification)} · {levelsLabel(command.data.applicable_year_levels, command.data.year_level_policy_status)}</p><p>These settings affect future academic eligibility. Submitted Inventories and issued certificates are not recalculated.</p></div> : null}
    {command.operation === "status" ? <>
      <p>Status: {command.target.record.is_active ? "Active" : "Inactive"} → <strong>{command.data.is_active ? "Active" : "Inactive"}</strong></p>
      <p>{command.data.is_active ? "Parent records must be active and Programs need complete settings. Descendants and historical assignments are not restored automatically." : "New use of this record will be restricted. No descendants or assignments are changed automatically. Historical facts are preserved; access through current scope may change."}</p>
      {impact ? <>
        {impact.blockers.length ? <div><p className="font-semibold">Blockers</p><ul>{impact.blockers.map((issue) => <li key={issue.code}>{impactExplanations[issue.code]} Count: {issue.count}.</li>)}</ul></div> : null}
        {impact.warnings.length ? <div><p className="font-semibold">Warnings</p><ul>{impact.warnings.map((issue) => <li key={issue.code}>{impactExplanations[issue.code]} Count: {issue.count}.</li>)}</ul></div> : null}
        <p>Preserved references: {impact.preserved_categories.map(preservedCategoryLabel).join(", ")}.</p>
        <p>Linked records will be checked again when you save.</p>
      </> : null}
    </> : null}
    {target ? <p>{command.operation === "rename" ? `Code: ${target.record.code} · ` : ""}{parentLabel(target)}</p> : <p>Initial status: {"is_active" in data && data.is_active ? "Active" : "Inactive"}</p>}
    {parent ? <p>Parent: {parent.record.name} ({parent.record.code}) · {parentLabel(parent)}</p> : null}
    <p className="break-words">Change note: {data.basis}</p>
  </>;
}
