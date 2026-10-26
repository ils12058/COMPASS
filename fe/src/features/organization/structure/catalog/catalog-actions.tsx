import { Button } from "@/components/ui/button";
import type { CatalogIntent, CatalogTarget } from "./catalog-model";

export function CatalogActions({ target, disabled, onEdit, onHistory }: {
  target: CatalogTarget; disabled: boolean;
  onEdit: (intent: CatalogIntent, opener: HTMLElement) => void;
  onHistory: (target: CatalogTarget, opener: HTMLElement) => void;
}) {
  return <details className="mt-2 text-sm">
    <summary className="min-h-11 cursor-pointer py-2 font-semibold text-brand">Actions <span className="sr-only">for {target.record.name}</span></summary>
    <div className="flex flex-wrap gap-2 py-2">
      {target.kind === "campus" ? <Button variant="secondary" disabled={disabled} onClick={(event) => onEdit({ mode: "create", kind: "college", parent: target }, event.currentTarget)}>Add college</Button> : target.kind === "college" ? <Button variant="secondary" disabled={disabled} onClick={(event) => onEdit({ mode: "create", kind: "program", parent: target }, event.currentTarget)}>Add program</Button> : null}
      <Button variant="secondary" disabled={disabled} onClick={(event) => onEdit({ mode: "rename", target }, event.currentTarget)}>Rename</Button>
      {target.kind === "program" ? <Button variant="secondary" disabled={disabled} onClick={(event) => onEdit({ mode: "policy", target }, event.currentTarget)}>Edit academic policy</Button> : null}
      <Button variant="secondary" disabled={disabled} onClick={(event) => onHistory(target, event.currentTarget)}>Change history</Button>
      <Button variant="secondary" disabled={disabled} onClick={(event) => onEdit({ mode: "status", target }, event.currentTarget)}>{target.record.is_active ? "Deactivate" : "Activate"}</Button>
    </div>
  </details>;
}
