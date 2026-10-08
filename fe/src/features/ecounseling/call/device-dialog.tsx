"use client";

import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import type { CallDevices, DeviceOption } from "./call-model";

type DeviceKind = "camera" | "microphone" | "speaker";

const failureCopy: Record<DeviceKind, string> = {
  camera: "Couldn’t switch to that camera. Choose another one.",
  microphone: "Couldn’t switch to that microphone. Choose another one.",
  speaker: "Couldn’t switch to that speaker. Your system default is still used.",
};

function DeviceField({
  kind,
  label,
  options,
  value,
  onSelect,
}: {
  kind: DeviceKind;
  label: string;
  options: DeviceOption[];
  value: string | null;
  onSelect: (kind: DeviceKind, id: string) => Promise<void>;
}) {
  const id = useId();
  const errorId = `${id}-error`;
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function choose(next: string) {
    setPending(true);
    setFailed(false);
    try {
      await onSelect(kind, next);
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      {options.length ? (
        <Select
          id={id}
          className="mt-1.5"
          // Reflects the device Daily reports as selected, so a disconnected device is never kept.
          value={value ?? ""}
          disabled={pending}
          aria-invalid={failed || undefined}
          aria-describedby={failed ? errorId : undefined}
          onChange={(event) => void choose(event.target.value)}
        >
          {value === null ? <option value="" disabled>Choose a {label.toLowerCase()}</option> : null}
          {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
        </Select>
      ) : (
        <p id={id} className="mt-1.5 text-sm text-muted">
          {kind === "speaker" ? "Uses your system default" : `No ${label.toLowerCase()} found`}
        </p>
      )}
      {failed ? <p id={errorId} role="alert" className="mt-1.5 text-sm text-danger">{failureCopy[kind]}</p> : null}
    </div>
  );
}

// Camera, microphone and, where the browser supports choosing one, speaker. Choices apply at once
// through Daily; the lists follow devices connected or removed while the dialog is open.
export function DeviceDialog({
  open,
  onOpenChange,
  devices,
  onRefresh,
  onSelectCamera,
  onSelectMicrophone,
  onSelectSpeaker,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  devices: CallDevices;
  onRefresh: () => Promise<void>;
  onSelectCamera: (id: string) => Promise<void>;
  onSelectMicrophone: (id: string) => Promise<void>;
  onSelectSpeaker: (id: string) => Promise<void>;
}) {
  useEffect(() => {
    if (open) void onRefresh();
  }, [open, onRefresh]);

  const select = (kind: DeviceKind, id: string) =>
    kind === "camera" ? onSelectCamera(id) : kind === "microphone" ? onSelectMicrophone(id) : onSelectSpeaker(id);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel="Close devices">
        <DialogTitle>Devices</DialogTitle>
        <DialogDescription>Changes apply to this call right away.</DialogDescription>
        <div className="mt-5 space-y-4">
          <DeviceField kind="camera" label="Camera" options={devices.cameras} value={devices.camera} onSelect={select} />
          <DeviceField kind="microphone" label="Microphone" options={devices.microphones} value={devices.microphone} onSelect={select} />
          <DeviceField kind="speaker" label="Speaker" options={devices.speakerSelectable ? devices.speakers : []} value={devices.speaker} onSelect={select} />
        </div>
        <div className="mt-6 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary">Done</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}
