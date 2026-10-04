import { RevisionStatusValue, type RevisionResponse } from "@/lib/api/generated/model";

// How the saved draft compares with the version an open editor started from.
// "saved-elsewhere": someone saved the draft since; local edits can be reviewed and kept.
// "no-longer-draft": it was published, so it can no longer be edited at all.
// "retired": its notice was retired, so it can no longer be edited at all.
export type DraftConflict = "saved-elsewhere" | "no-longer-draft" | "retired";

export function draftConflict({
  baseUpdatedAt,
  latest,
  noticeActive,
}: {
  baseUpdatedAt: string;
  latest: Pick<RevisionResponse, "status" | "updated_at">;
  noticeActive: boolean | undefined;
}): DraftConflict | null {
  if (noticeActive === false) return "retired";
  if (latest.status !== RevisionStatusValue.DRAFT) return "no-longer-draft";
  if (latest.updated_at !== baseUpdatedAt) return "saved-elsewhere";
  return null;
}

export const draftConflictMessages: Record<DraftConflict, string> = {
  "saved-elsewhere":
    "This draft was saved elsewhere while you were editing. Your unsaved changes are kept here. Review the latest saved version before saving again.",
  "no-longer-draft":
    "This draft was published while you were editing, so it can no longer be changed. Your unsaved text is kept here so you can copy it into a new revision.",
  retired:
    "This notice was retired while you were editing, so the draft can no longer be saved. Your unsaved text is kept here.",
};
