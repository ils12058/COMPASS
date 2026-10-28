import Link from "next/link";
import type { CatalogDependentCounts, CatalogImpactResponse, CatalogIssueCode } from "@/lib/api/generated/model";

export const impactExplanations: Record<CatalogIssueCode, string> = {
  active_child_colleges: "Active colleges remain. Review them before deactivating this campus.",
  active_child_programs: "Active programs remain. Review them before deactivating this college.",
  active_student_affiliations: "Students are still linked to this scope. Their affiliations need review before deactivation.",
  counselor_responsibilities: "A Counselor responsibility remains. Remove or update it before deactivation.",
  open_office_threads: "Open guidance conversations depend on this scope. Resolve the affected work before deactivation.",
  pending_operational_followups: "Pending operational Follow-Ups depend on this scope. Review the affected work before deactivation.",
  inactive_account_affiliations: "Affiliations for inactive accounts are retained. Account reactivation will require usable parent records.",
  draft_inventories: "Draft Inventories are retained. Future selection or submission will need an active Program and valid academic policy.",
  pending_good_moral: "Pending Good Moral requests are retained. Review their existing academic and certificate requirements separately.",
};
const countLabels: Record<keyof CatalogDependentCounts, string> = {
  active_child_colleges: "Active colleges", active_child_programs: "Active programs",
  active_student_affiliations: "Active Student affiliations", child_colleges: "All colleges", child_programs: "All programs",
  counselor_responsibilities: "Counselor responsibilities", draft_inventories: "Draft Inventories",
  graduate_tracer_references: "Graduate Tracer references", inactive_account_affiliations: "Inactive-account affiliations",
  issued_good_moral: "Issued Good Moral certificates", open_office_threads: "Open Office conversations",
  pending_f4: "Pending Good Moral F4 requests", pending_good_moral: "All pending Good Moral requests",
  pending_operational_followups: "Pending operational Follow-Ups", resolved_threads: "Resolved conversations",
  student_affiliations: "All Student affiliations", submitted_inventories: "Submitted Inventories",
};
export function preservedCategoryLabel(value: string) {
  const labels: Record<string, string> = {
    submitted_inventory_facts: "Submitted Inventory facts", issued_certificate_snapshots: "Issued certificate snapshots",
    graduate_tracer_references: "Graduate Tracer references", resolved_guidance_threads: "Resolved guidance conversations",
    inactive_affiliations: "Inactive affiliations",
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
    {canManageRelationships && impact.blockers.some((issue) => issue.code === "active_student_affiliations" || issue.code === "counselor_responsibilities") ? <p className="flex flex-wrap gap-3">
      {impact.blockers.some((issue) => issue.code === "active_student_affiliations") ? <Link className="text-brand underline" href="/portal/organization/student-affiliations">Review Student affiliations</Link> : null}
      {impact.blockers.some((issue) => issue.code === "counselor_responsibilities") ? <Link className="text-brand underline" href="/portal/organization/responsibilities">Review Responsibilities</Link> : null}
    </p> : null}
    <details><summary className="min-h-11 cursor-pointer py-2 font-semibold">Dependent-record counts</summary>
      <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-2">{Object.entries(countLabels).map(([key, label]) => <Count key={key} label={label} value={impact.counts[key as keyof CatalogDependentCounts]} />)}</dl>
    </details>
    <div><h4 className="font-semibold">Preserved references</h4><ul className="mt-1 list-inside list-disc">{impact.preserved_categories.map((category) => <li key={category}>{preservedCategoryLabel(category)}</li>)}</ul>
      <p className="mt-2 text-muted">No child is deactivated or reassigned automatically. Saved historical facts remain; current scope can affect access to resolved work.</p>
    </div>
  </section>;
}
function Count({ label, value }: { label: string; value: number }) { return <><dt>{label}</dt><dd className="tabular-nums">{value}</dd></>; }
