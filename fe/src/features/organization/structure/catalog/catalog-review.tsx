import type { CatalogImpactResponse } from "@/lib/api/generated/model";
import { impactExplanations, preservedCategoryLabel } from "./catalog-impact";
import { classificationLabel, levelsLabel, parentLabel, type CatalogCommand, type CatalogTarget } from "./catalog-model";

export function CatalogReview({ command, impact, parent }: { command: CatalogCommand; parent?: CatalogTarget; impact?: CatalogImpactResponse }) {
  const target = "target" in command ? command.target : undefined;
  const data = command.data;
  return <>
    <p className="break-words font-semibold">{target?.record.name ?? ("name" in data ? data.name : "")} · {target?.record.code ?? ("code" in data ? data.code : "")}</p>
    {target ? <><p>{parentLabel(target)}</p><p>Reviewed version: {target.record.resource_version}</p></> : <p>Initial status: {"is_active" in data && data.is_active ? "Active" : "Inactive"}</p>}
    {parent ? <p>Fixed parent: {parent.record.name} ({parent.record.code}) · {parentLabel(parent)}</p> : null}
    {command.operation === "rename" ? <><p>Current name: {command.target.record.name}</p><p>Proposed official name: <strong>{command.data.name}</strong></p><p>Current linked labels may change. Saved historical facts remain; finalized documents are not regenerated.</p></> : null}
    {command.operation === "policy" ? <div><p className="font-semibold">Current academic policy</p><p>{classificationLabel(command.target.record.academic_classification)} · {command.target.record.year_level_policy_status === "CONFIGURED" ? "Configured" : "Pending"} · {levelsLabel(command.target.record.applicable_year_levels, command.target.record.year_level_policy_status)}</p></div> : null}
    {command.operation === "policy" || command.operation === "createProgram" ? <div><p className="font-semibold">Proposed academic policy</p><p>{classificationLabel(command.data.academic_classification)} · {command.data.year_level_policy_status === "CONFIGURED" ? "Configured" : "Pending"} · {levelsLabel(command.data.applicable_year_levels, command.data.year_level_policy_status)}</p><p>Future academic validation uses this policy. Existing submitted Inventories and issued certificates are not recalculated.</p></div> : null}
    {command.operation === "status" ? <>
      <p>Status: {command.target.record.is_active ? "Active" : "Inactive"} → <strong>{command.data.is_active ? "Active" : "Inactive"}</strong></p>
      <p>{command.data.is_active ? "Active parent ancestry and complete Program policy are checked by the server. Descendants and historical assignments are not restored automatically." : "New use of this record will be restricted. No descendants or assignments are changed automatically. Historical facts are preserved; access through current scope may change."}</p>
      {impact ? <><p>Impact reviewed at {new Date(impact.observed_at).toLocaleString()}, version {impact.resource_version}. The server recomputes blockers before saving.</p>
        {impact.warnings.length ? <ul>{impact.warnings.map((issue) => <li key={issue.code}>{impactExplanations[issue.code]} Count: {issue.count}.</li>)}</ul> : null}
        <p>Preserved references: {impact.preserved_categories.map(preservedCategoryLabel).join(", ")}.</p></> : null}
    </> : null}
    <p className="break-words">Basis/reference: {data.basis}</p>
  </>;
}
