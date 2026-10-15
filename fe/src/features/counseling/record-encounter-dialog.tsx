"use client";

import { useState } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { RecordEncounterForm, encounterProvenanceNote, type EncounterOriginPreset, type EncounterTimes } from "@/features/counseling/record-encounter-form";

// Only the short preset form belongs here. Student/Appointment search and corrections retain
// their larger page surfaces. Times survive dismissal; pending saves stay open, and an unconfirmed
// result closes only through its own Close.
export function RecordEncounterDialog({ open, onOpenChange, preset, onCreated, onUncertain, onAlreadyRecorded, onCloseAutoFocus }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preset: EncounterOriginPreset;
  onCreated: () => void | Promise<void>;
  onUncertain?: () => void;
  onAlreadyRecorded?: () => void | Promise<void>;
  // Where focus goes when the opener was replaced, e.g. by View encounter after recording.
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const [times, setTimes] = useState<EncounterTimes>({ startedAt: "", endedAt: "" });
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl" dismissible={!busy} onCloseAutoFocus={onCloseAutoFocus}>
        <DialogTitle>Record encounter</DialogTitle>
        <DialogDescription>{encounterProvenanceNote(preset.entryMode)}</DialogDescription>
        <div className="mt-5">
          <RecordEncounterForm
            framed={false}
            preset={preset}
            initialTimes={times}
            onTimesChange={setTimes}
            onBusyChange={setBusy}
            onCancel={() => onOpenChange(false)}
            onUncertain={onUncertain}
            onAlreadyRecorded={onAlreadyRecorded}
            onCreated={async () => { await onCreated(); setTimes({ startedAt: "", endedAt: "" }); }}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
