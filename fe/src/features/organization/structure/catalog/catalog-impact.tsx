import Link from "next/link";
import type { CatalogDependentCounts, CatalogImpactResponse, CatalogIssueCode } from "@/lib/api/generated/model";

export const impactExplanations: Record<CatalogIssueCode, string> = {
  active_child_colleges: "Active colleges remain. Review them before deactivating this campus.",
  active_child_programs: "Active programs remain. Review them before deactivating this college.",
  active_faculty_affiliations: "Active Faculty accounts still belong to this Campus or College. Review their home Colleges in Accounts before deactivation.",
  inactive_faculty_affiliations: "Inactive Faculty references are retained; reactivation requires an active College and Campus.",
  active_student_placements: "Students still have placements in this Campus, College or Program. Review their placements before deactivation.",
  counselor_responsibilities: "A Counselor responsibility remains. Remove or update it before deactivation.",
  open_office_threads: "Open Guidance Office conversations belong to this Campus or College. Close the affected conversations before deactivation.",
  pending_operational_followups: "Pending Follow-Ups belong to this Campus or College. Review them before deactivation.",
  inactive_student_placements: "Placements for inactive accounts are retained. Account reactivation will require usable parent records.",
  draft_inventories: "Draft Individual Inventories are retained. Future selection or submission will need an active Program and valid academic policy.",
  pending_good_moral: "Pending Good Moral Certificate requests stay saved. Review their academic and certificate requirements separately.",
};
const countLabels: Record<keyof CatalogDependentCounts, string> = {
  active_child_colleges: "Active colleges", active_child_programs: "Active programs",
  faculty_affiliations: "All Faculty affiliations", active_faculty_affiliations: "Active Faculty affiliations", inactive_faculty_affiliations: "Inactive Faculty affiliations",
  active_student_placements: "Active Student placements", child_colleges: "All colleges", child_programs: "All programs",
  counselor_responsibilities: "Counselor responsibilities", draft_inventories: "Draft Individual Inventories",
  graduate_tracer_references: "Graduate Tracer references", inactive_student_placements: "Inactive-account placements",
  issued_good_moral: "Issued Good Moral Certificates", open_office_threads: "Open Office conversations",
  pending_f4: "Pending Good Moral Certificate requests for current Students (F4)", pending_good_moral: "All pending Good Moral Certificate requests",
  pending_operational_followups: "Pending Follow-Ups", resolved_threads: "Closed conversations",
  student_placements: "All Student placements", submitted_inventories: "Submitted Individual Inventories",
};
export function preservedCategoryLabel(value: string) {
  const labels: Record<string, string> = {
    submitted_inventory_facts: "Submitted Individual Inventory facts", issued_certificate_snapshots: "Issued certificates",
    graduate_tracer_references: "Graduate Tracer references", resolved_guidance_threads: "Closed Guidance Office conversations",
    inactive_placements: "Inactive placements",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}
export function CatalogImpact({ impact, canManageRelationships }: { impact: CatalogImpactResponse; canManageRelationships: boolean }) {
  return <section aria-labelledby="catalog-impact-heading" className="space-y-4 text-sm">
    <h3 id="catalog-impact-heading" className="font-heading text-lg font-semibold">Deactivation impact</h3>
    <p className="font-semibold">{impact.can_deactivate ? "No blockers found" : "Deactivation blocked"}</p>
    <p className="text-muted">Linked records will be checked again when you save.</p>
    {impact.blockers.length ? <div>
      <h4 className="font-semibold">Blockers</h4>
      <ul className="mt-1 space-y-2">{impact.blockers.map((issue) => <li key={issue.code}>{impactExplanations[issue.code]} <strong>Count: {issue.count}</strong></li>)}</ul>
    </div> : null}
    {impact.warnings.length ? <div><h4 className="font-semibold">Warnings</h4><ul className="mt-1 space-y-2">{impact.warnings.map((issue) => <li key={issue.code}>{impactExplanations[issue.code]} <strong>Count: {issue.count}</strong></li>)}</ul></div> : null}
    {canManageRelationships && impact.blockers.some((issue) => issue.code === "active_student_placements" || issue.code === "counselor_responsibilities") ? <p className="flex flex-wrap gap-3">
      {impact.blockers.some((issue) => issue.code === "active_student_placements") ? <Link className="text-brand underline" href="/portal/organization/student-academics">Review Student placements</Link> : null}
      {impact.blockers.some((issue) => issue.code === "counselor_responsibilities") ? <Link className="text-brand underline" href="/portal/organization/responsibilities">Review Responsibilities</Link> : null}
    </p> : null}
    <details><summary className="min-h-11 cursor-pointer py-2 font-semibold">Linked records</summary>
      <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-2">{Object.entries(countLabels).map(([key, label]) => <Count key={key} label={label} value={impact.counts[key as keyof CatalogDependentCounts]} />)}</dl>
    </details>
    <div><h4 className="font-semibold">Records kept</h4><ul className="mt-1 list-inside list-disc">{impact.preserved_categories.map((category) => <li key={category}>{preservedCategoryLabel(category)}</li>)}</ul>
      <p className="mt-2 text-muted">Linked Colleges and Programs aren&apos;t deactivated or reassigned automatically. Past records stay as they are; people may lose access to closed work that belongs to this Campus, College or Program.</p>
    </div>
  </section>;
}
function Count({ label, value }: { label: string; value: number }) { return <><dt>{label}</dt><dd className="tabular-nums">{value}</dd></>; }
