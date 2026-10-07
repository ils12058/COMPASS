"use client";

import { useState } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { RecordEncounterForm, type EncounterOriginPreset, type EncounterTimes } from "@/features/counseling/record-encounter-form";

// Only the short preset form belongs here. Student/Appointment search and corrections retain
// their larger page surfaces. Times survive dismissal; pending and uncertain saves stay open.
export function RecordEncounterDialog({ open, onOpenChange, preset, onCreated, onUncertain, onAlreadyRecorded }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preset: EncounterOriginPreset;
  onCreated: () => void | Promise<void>;
  onUncertain?: () => void;
  onAlreadyRecorded?: () => void | Promise<void>;
}) {
  const [times, setTimes] = useState<EncounterTimes>({ startedAt: "", endedAt: "" });
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl" dismissible={!busy}>
        <DialogTitle>Record encounter</DialogTitle>
        <DialogDescription>Enter the actual times of the completed interaction.</DialogDescription>
        <div className="mt-5">
          <RecordEncounterForm
            preset={preset}
            initialTimes={times}
            onTimesChange={setTimes}
            onBusyChange={setBusy}
            onUncertain={onUncertain}
            onAlreadyRecorded={onAlreadyRecorded}
            onCreated={async () => { await onCreated(); setTimes({ startedAt: "", endedAt: "" }); }}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
