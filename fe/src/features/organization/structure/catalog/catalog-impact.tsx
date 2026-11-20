import { useId } from "react";
import type { CatalogDependentCounts, CatalogImpactResponse, CatalogIssueSummary } from "@/lib/api/generated/model";

export function warningMessage(issue: CatalogIssueSummary, kind: string) {
  const count = issue.count;
  switch (issue.code) {
    case "active_student_placements": return `${count} active student${count === 1 ? " is" : "s are"} still placed in this ${kind}. They keep their current placement; it won't be offered for new records.`;
    case "active_faculty_affiliations": return `${count} active faculty affiliation${count === 1 ? " remains" : "s remain"}. Faculty keep their current affiliation.`;
    case "counselor_responsibilities": return `${count} counselor responsibilit${count === 1 ? "y remains" : "ies remain"}. Existing responsibilities keep working.`;
    case "open_office_threads": return `${count} open Guidance Office conversation${count === 1 ? " remains" : "s remain"}. They stay available to the people who can use them.`;
    case "pending_operational_followups": return `${count} pending follow-up${count === 1 ? " remains" : "s remain"}. Existing follow-ups keep working.`;
    case "inactive_student_placements": return `${count} placement${count === 1 ? " for an inactive account is" : "s for inactive accounts are"} kept.`;
    case "inactive_faculty_affiliations": return `${count} inactive faculty affiliation${count === 1 ? " is" : "s are"} kept.`;
    case "draft_inventories": return `${count} draft Individual Inventor${count === 1 ? "y is" : "ies are"} kept. Selecting or submitting a program still requires an active program and complete settings.`;
    case "pending_good_moral": return `${count} pending Good Moral request${count === 1 ? " is" : "s are"} kept. Certificate requirements still apply.`;
    case "active_child_colleges": return `${count} active college${count === 1 ? " is" : "s are"} under this campus.`;
    case "active_child_programs": return `${count} active program${count === 1 ? " is" : "s are"} under this record.`;
  }
}
const countLabels: Record<keyof CatalogDependentCounts, string> = {
  active_child_colleges: "Active colleges", active_child_programs: "Active programs",
  faculty_affiliations: "All faculty affiliations", active_faculty_affiliations: "Active faculty affiliations", inactive_faculty_affiliations: "Inactive faculty affiliations",
  active_student_placements: "Active student placements", child_colleges: "All colleges", child_programs: "All programs",
  counselor_responsibilities: "Counselor responsibilities", draft_inventories: "Draft Individual Inventories",
  graduate_tracer_references: "Graduate Tracer references", inactive_student_placements: "Placements for inactive accounts",
  issued_good_moral: "Issued Good Moral certificates", open_office_threads: "Open Guidance Office conversations",
  pending_f4: "Pending Good Moral requests for current students", pending_good_moral: "All pending Good Moral requests",
  pending_operational_followups: "Pending follow-ups", resolved_threads: "Closed conversations",
  student_placements: "All student placements", submitted_inventories: "Submitted Individual Inventories",
};
export function preservedCategoryLabel(value: string) {
  const labels: Record<string, string> = {
    submitted_inventory_facts: "Submitted Individual Inventory facts", issued_certificate_snapshots: "Issued certificates",
    graduate_tracer_references: "Graduate Tracer references", resolved_guidance_threads: "Closed Guidance Office conversations",
    inactive_placements: "Placements for inactive accounts",
  };
  return labels[value] ?? "Other saved records";
}
export function cascadeLabel(impact: CatalogImpactResponse) {
  const colleges = impact.counts.active_child_colleges;
  const programs = impact.counts.active_child_programs;
  const parts = [colleges ? `${colleges} active college${colleges === 1 ? "" : "s"}` : "", programs ? `${programs} active program${programs === 1 ? "" : "s"}` : ""].filter(Boolean);
  return `Also retire the ${parts.join(" and ")} under it`;
}
export function CatalogImpact({ impact, kind = "record" }: { impact: CatalogImpactResponse; kind?: string }) {
  const headingId = useId();
  return <section aria-labelledby={headingId} className="space-y-4 text-sm">
    <h3 id={headingId} className="font-heading text-lg font-semibold">Retirement impact</h3>
    <p>This {kind} won&apos;t be offered for new records. Existing placements, affiliations, counselor responsibilities, conversations and follow-ups stay as they are.</p>
    {impact.warnings.length ? <div><h4 className="font-semibold">Existing records kept</h4><ul className="mt-1 space-y-2">{impact.warnings.map((issue) => <li key={issue.code}>{warningMessage(issue, kind)}</li>)}</ul></div> : null}
    {impact.active_children.length ? <div><h4 className="font-semibold">Active colleges and programs under it</h4><ul className="mt-1 list-inside list-disc">{impact.active_children.map((child) => <li key={child.id}>{child.name} ({child.code}) · {child.kind === "college" ? "College" : "Program"}</li>)}</ul><p className="mt-2">Retire these together with the {kind} in the confirmation to continue.</p></div> : null}
    <details><summary className="min-h-11 cursor-pointer py-2 font-semibold">Linked records</summary>
      <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-2">{Object.entries(countLabels).map(([key, label]) => <Count key={key} label={label} value={impact.counts[key as keyof CatalogDependentCounts]} />)}</dl>
    </details>
    <p>Records kept: {impact.preserved_categories.map(preservedCategoryLabel).join(", ")}.</p>
  </section>;
}
function Count({ label, value }: { label: string; value: number }) { return <><dt>{label}</dt><dd className="tabular-nums">{value}</dd></>; }
