// The Referral status note editor keeps the person's text across reloads of the Referral. A reload
// that changes only other fields leaves the text alone. A newer saved note replaces text that was
// not changed, and never replaces text that was: the editor reports the change, and saving waits
// until the person keeps their text or cancels.

export type StatusNoteDraft = {
  editing: boolean;
  value: string;
  // The saved note the text builds on.
  baseline: string;
};

export function startStatusNoteDraft(savedNote: string): StatusNoteDraft {
  return { editing: false, value: savedNote, baseline: savedNote };
}

export function statusNoteDirty(draft: StatusNoteDraft): boolean {
  return draft.editing && draft.value !== draft.baseline;
}

// Follows a newer saved note unless the person has changed the text. Returns the same draft when
// nothing changes, so a component can adjust its state while rendering.
export function reconcileStatusNote(draft: StatusNoteDraft, savedNote: string): StatusNoteDraft {
  if (savedNote === draft.baseline || statusNoteDirty(draft)) return draft;
  return { ...draft, value: savedNote, baseline: savedNote };
}

// The saved note changed while the person had unsaved text.
export function statusNoteConflict(draft: StatusNoteDraft, savedNote: string): boolean {
  return statusNoteDirty(draft) && savedNote !== draft.baseline;
}

// The person reviewed the newer saved note and keeps their text; saving replaces that note.
export function keepStatusNoteText(draft: StatusNoteDraft, savedNote: string): StatusNoteDraft {
  return { ...draft, baseline: savedNote };
}
