"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Notice } from "@/components/ui/notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { TableSkeleton } from "@/features/organization/components/organization-shared";
import type { CatalogHistoryValues } from "@/lib/api/generated/model";
import { catalogErrorMessage } from "./catalog-errors";
import { classificationLabel, levelsLabel, parentLabel, type CatalogTarget } from "./catalog-model";
import { catalogHistoryKey, readCatalogHistory } from "./catalog-query";

export function HistoryValues({ values }: { values: CatalogHistoryValues }) {
  return <ul className="space-y-1 break-words">
    {values.name !== undefined ? <li>Official name: {values.name}</li> : null}
    {typeof values.is_active === "boolean" ? <li>Status: {values.is_active ? "Active" : "Inactive"}</li> : null}
    {values.academic_classification !== undefined ? <li>{classificationLabel(values.academic_classification)}</li> : null}
    {values.year_level_policy_status !== undefined ? <li>Year levels: {values.year_level_policy_status === "CONFIGURED" ? "Set" : "Not set yet"}</li> : null}
    {values.applicable_year_levels !== undefined ? <li>{levelsLabel(values.applicable_year_levels, values.year_level_policy_status)}</li> : null}
  </ul>;
}
function changeLabel(action: string) {
  return action.endsWith(".created") ? "Created" : action.endsWith(".policy_changed") ? "Program settings changed" : action.endsWith(".enabled") ? "Activated" : action.endsWith(".disabled") ? "Deactivated" : "Official name changed";
}
export function CatalogHistory({ target, onClose, onCloseAutoFocus }: { target: CatalogTarget; onClose: () => void; onCloseAutoFocus: (event: Event) => void }) {
  const [page, setPage] = useState(1);
  const history = useQuery({ queryKey: [...catalogHistoryKey(target.kind, target.record.id, page), "catalog-presentation"], queryFn: ({ signal }) => readCatalogHistory(target.kind, target.record.id, page, signal), retry: false, staleTime: 0 });
  return <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
    <DialogContent className="max-w-2xl" onCloseAutoFocus={onCloseAutoFocus}>
      <DialogTitle>Change history: {target.record.name}</DialogTitle>
      <DialogDescription>{target.record.code} · {parentLabel(target)}. Only recorded changes for this record are shown. Earlier initialization events are not included.</DialogDescription>
      <div className="mt-5 space-y-4">
        {history.isPending ? <TableSkeleton label="Loading change history…" /> : history.isError ? <Notice tone="danger" role="alert" action={<Button variant="secondary" onClick={() => void history.refetch()}>Retry</Button>}>{catalogErrorMessage(history.error)}</Notice> : history.data ? <>
          {history.data.items.length ? <ol className="divide-y divide-border">{history.data.items.map((item) => <li key={item.id} className="space-y-2 py-4 text-sm">
            <h3 className="font-semibold">{changeLabel(item.action)}</h3>
            <p>{new Date(item.occurred_at).toLocaleString()}</p>
            <div className="grid gap-3 sm:grid-cols-2"><div><h4 className="font-semibold">Before</h4>{Object.keys(item.before).length ? <HistoryValues values={item.before} /> : <p>New record</p>}</div><div><h4 className="font-semibold">After</h4><HistoryValues values={item.after} /></div></div>
            <p className="break-words">Change note: {item.basis}</p>
          </li>)}</ol> : <p className="text-sm text-muted">No recorded changes on this page. Earlier initialization events are not included here.</p>}
          <CanonicalPagination page={history.data.page} hasNext={history.data.has_next} onPageChange={setPage} />
        </> : null}
        <div className="flex justify-end"><Button variant="secondary" onClick={onClose}>Close history</Button></div>
      </div>
    </DialogContent>
  </Dialog>;
}
