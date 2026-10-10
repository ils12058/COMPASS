// Generic availability only. Legacy, Retired and workflow states keep their domain labels.
export function ActiveStatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${
        active
          ? "border-success/30 bg-success/10 text-success"
          : "border-border bg-surface-muted text-muted"
      }`}
    >
      {active ? "Active" : "Inactive"}
    </span>
  );
}
