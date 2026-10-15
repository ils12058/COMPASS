"use client";

import { useId } from "react";

import {
  inventoryCorrectionTargetLabel,
  readInventoryCorrectionTargets,
} from "@/features/inventory/inventory-correction-targets";
import { formatInventoryDate, InventoryNotice } from "@/features/inventory/inventory-shared";
import type { InventoryCorrectionSummary, InventoryCorrectionTarget } from "@/lib/api/generated/model";

// The pending correction request a Student sees: the Counselor's instructions and, when the
// request named them, the answers to review. Only the editable draft passes onSelectTarget; every
// other view lists the answers as plain text, so a record that cannot be edited never looks
// editable.
export function InventoryCorrectionNotice({
  correction,
  onSelectTarget,
}: {
  correction: InventoryCorrectionSummary;
  onSelectTarget?: (target: InventoryCorrectionTarget) => void;
}) {
  const listId = useId();
  const { targets, unknown } = readInventoryCorrectionTargets(correction.targets);
  return (
    <InventoryNotice title="Correction requested" tone="warning">
      <p className="whitespace-pre-wrap">{correction.message}</p>
      {targets.length || unknown ? (
        <div className="mt-3">
          <p id={`${listId}-heading`} className="font-semibold text-ink">Answers to review</p>
          {onSelectTarget ? (
            <p id={`${listId}-help`} className="text-xs leading-5 text-muted">Select an answer to go to it in the form.</p>
          ) : null}
          <ul aria-labelledby={`${listId}-heading`} className={onSelectTarget ? "mt-1 space-y-0.5 text-ink" : "mt-1.5 list-disc space-y-1 pl-5 text-ink"}>
            {targets.map((target) => (
              <li key={target}>
                {onSelectTarget ? (
                  <button
                    type="button"
                    aria-describedby={`${listId}-help`}
                    className="inline-flex min-h-9 items-center rounded-sm text-left font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    onClick={() => onSelectTarget(target)}
                  >
                    {inventoryCorrectionTargetLabel(target)}
                  </button>
                ) : (
                  inventoryCorrectionTargetLabel(target)
                )}
              </li>
            ))}
            {unknown ? (
              <li>{unknown === 1 ? "1 more part of the form" : `${unknown} more parts of the form`}</li>
            ) : null}
          </ul>
        </div>
      ) : null}
      <p className="mt-2 text-xs text-muted">Requested {formatInventoryDate(correction.requested_at)}</p>
    </InventoryNotice>
  );
}
