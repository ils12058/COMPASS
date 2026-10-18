"use client";

import { LoaderCircle, RotateCw } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import type { CallDevices, DeviceOption } from "./call-model";

export type DeviceKind = "camera" | "microphone" | "speaker";

const failureCopy: Record<DeviceKind, string> = {
  camera: "Couldn’t switch to that camera. Choose another one.",
  microphone: "Couldn’t switch to that microphone. Choose another one.",
  speaker: "Couldn’t switch to that speaker. Your system default is still used.",
};

export function DeviceField({
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
  description = "Changes apply to this call right away.",
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  devices: CallDevices;
  onRefresh: () => Promise<void>;
  onSelectCamera: (id: string) => Promise<void>;
  onSelectMicrophone: (id: string) => Promise<void>;
  onSelectSpeaker: (id: string) => Promise<void>;
  description?: string;
  children?: ReactNode;
}) {
  const [refreshing, setRefreshing] = useState(false);
  const refreshInFlightRef = useRef(false);

  const refreshDevices = useCallback(async () => {
    if (refreshInFlightRef.current) return;
    refreshInFlightRef.current = true;
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      refreshInFlightRef.current = false;
      setRefreshing(false);
    }
  }, [onRefresh]);

  useEffect(() => {
    if (open) void refreshDevices();
  }, [open, refreshDevices]);

  const select = (kind: DeviceKind, id: string) =>
    kind === "camera" ? onSelectCamera(id) : kind === "microphone" ? onSelectMicrophone(id) : onSelectSpeaker(id);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel="Close devices">
        <DialogTitle>Devices</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
        <div className="mt-4 flex justify-end">
          <Button type="button" variant="secondary" className="min-h-11" aria-busy={refreshing} disabled={refreshing} onClick={() => void refreshDevices()}>
            {refreshing ? <LoaderCircle aria-hidden="true" size={16} className="animate-spin motion-reduce:animate-none" /> : <RotateCw aria-hidden="true" size={16} />}
            {refreshing ? "Refreshing devices…" : "Refresh devices"}
          </Button>
        </div>
        <div className="mt-4 space-y-4">
          <DeviceField kind="camera" label="Camera" options={devices.cameras} value={devices.camera} onSelect={select} />
          <DeviceField kind="microphone" label="Microphone" options={devices.microphones} value={devices.microphone} onSelect={select} />
          <DeviceField kind="speaker" label="Speaker" options={devices.speakerSelectable ? devices.speakers : []} value={devices.speaker} onSelect={select} />
        </div>
        {children}
        <div className="mt-6 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary">Done</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}
