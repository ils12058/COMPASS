import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { OrganizationActionMessage } from "@/features/portal/admin/organization/portal-it-admin-organization-shared";
import type { PersonSummary } from "@/lib/api/generated/model";

export type PortalItAdminAssignmentTab =
  | "counselor-responsibilities"
  | "staff-supervision"
  | "student-affiliations";

export const ASSIGNMENT_TABS: readonly {
  label: string;
  value: PortalItAdminAssignmentTab;
}[] = [
  { label: "Counselor responsibilities", value: "counselor-responsibilities" },
  { label: "Staff supervision", value: "staff-supervision" },
  { label: "Student affiliations", value: "student-affiliations" },
];

export function AssignmentTabs({
  activeTab,
  onChange,
}: {
  activeTab: PortalItAdminAssignmentTab;
  onChange: (tab: PortalItAdminAssignmentTab) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Organization assignment areas"
      className="flex min-w-0 gap-1 overflow-x-auto rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-1"
    >
      {ASSIGNMENT_TABS.map((tab) => {
        const isActive = tab.value === activeTab;

        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={
              isActive
                ? "min-h-10 shrink-0 rounded-xl bg-card px-3 text-left text-sm font-semibold text-[var(--compass-brand-maroon)] shadow-sm"
                : "min-h-10 shrink-0 rounded-xl px-3 text-left text-sm font-semibold text-muted-foreground transition-colors hover:bg-card/70 hover:text-foreground"
            }
            onClick={() => onChange(tab.value)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

export function AssignmentSection({
  children,
  description,
  icon: Icon,
  title,
}: {
  children: ReactNode;
  description: string;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
      <header className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
          <Icon aria-hidden="true" className="size-5" />
        </span>
        <div className="min-w-0">
          <h2 className="font-heading text-2xl font-bold tracking-tight">{title}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
      </header>
      <div className="mt-6">{children}</div>
    </section>
  );
}

export function AssignmentPerson({ person }: { person: PersonSummary }) {
  return <span className="break-words font-semibold">{person.display_name}</span>;
}

export function AssignmentEmptyState({
  action,
  description,
  title,
}: {
  action?: ReactNode;
  description: string;
  title: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-8 text-center">
      <h3 className="font-heading text-xl font-bold">{title}</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
        {description}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function AssignmentQueryError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-6 text-center">
      <p role="alert" className="text-sm leading-6 text-muted-foreground">
        We couldn’t load these assignments right now.
      </p>
      <Button className="mt-4" type="button" variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

export function AssignmentListSkeleton() {
  return (
    <div className="space-y-3" aria-live="polite" aria-label="Loading assignments">
      {Array.from({ length: 4 }, (_, index) => (
        <div
          key={index}
          className="h-24 animate-pulse rounded-2xl bg-muted"
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

export { OrganizationActionMessage };
