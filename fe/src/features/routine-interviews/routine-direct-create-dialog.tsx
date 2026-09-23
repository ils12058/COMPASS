"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  routineDeliveryModeLabel,
  routineEntryModeLabel,
  routineErrorCode,
  routineErrorMessage,
} from "@/features/routine-interviews/routine-interviews-shared";
import {
  DeliveryMode,
  DirectRoutineEntryMode,
  type RoutineDirectStudentCandidate,
} from "@/lib/api/generated/model";
import {
  getRoutineInterviewsCreateDirectMutationKey,
  getRoutineInterviewsListAssignedQueryKey,
  routineInterviewsCreateDirect,
  useRoutineInterviewsGetDirectCreationOptions,
  useRoutineInterviewsListDirectStudentCandidates,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

const controlClass = "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

const entryModes = [
  DirectRoutineEntryMode.WALK_IN,
  DirectRoutineEntryMode.CALLED_IN,
  DirectRoutineEntryMode.REFERRED,
] as const;

export function RoutineDirectCreateDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && busyRef.current) return;
        onOpenChange(nextOpen);
      }}
    >
      {open ? (
        <DirectCreateForm
          onClose={() => onOpenChange(false)}
          onPendingChange={(pending) => {
            busyRef.current = pending;
            setBusy(pending);
          }}
          pending={busy}
        />
      ) : null}
    </Dialog>
  );
}

function DirectCreateForm({
  onClose,
  onPendingChange,
  pending,
}: {
  onClose: () => void;
  onPendingChange: (pending: boolean) => void;
  pending: boolean;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const intentRef = useRef<{ fingerprint: string; key: string } | null>(null);
  const [studentSearch, setStudentSearch] = useState("");
  const [candidateSearch, setCandidateSearch] = useState("");
  const [candidatePage, setCandidatePage] = useState(1);
  const [selectedStudent, setSelectedStudent] = useState<RoutineDirectStudentCandidate | null>(null);
  const [entryMode, setEntryMode] = useState<DirectRoutineEntryMode | "">("");
  const [selectedDeliveryMode, setSelectedDeliveryMode] = useState<DeliveryMode | "">("");
  const [error, setError] = useState<string | null>(null);

  const options = useRoutineInterviewsGetDirectCreationOptions({
    query: { retry: false },
  });
  const deliveryModes = options.data?.data.delivery_modes ?? [];
  const deliveryMode = selectedDeliveryMode || (deliveryModes.length === 1 ? deliveryModes[0] : "");
  const candidateParams = {
    ...(candidateSearch ? { search: candidateSearch } : {}),
    page: candidatePage,
    page_size: 8,
  };
  const candidates = useRoutineInterviewsListDirectStudentCandidates(candidateParams, {
    query: { enabled: options.isSuccess && deliveryModes.length > 0, retry: false },
  });
  const pageData = candidates.data?.data;
  const create = useMutation({
    mutationKey: getRoutineInterviewsCreateDirectMutationKey(),
    mutationFn: ({
      studentId,
      mode,
      delivery,
      key,
    }: {
      studentId: string;
      mode: DirectRoutineEntryMode;
      delivery: DeliveryMode;
      key: string;
    }) =>
      routineInterviewsCreateDirect(
        {
          student_id: studentId,
          entry_mode: mode,
          delivery_mode: delivery,
        },
        { headers: { "Idempotency-Key": key } },
      ),
  });

  function changeStudent(student: RoutineDirectStudentCandidate) {
    setSelectedStudent(student);
    intentRef.current = null;
    setError(null);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedStudent || !entryMode || !deliveryMode) return;
    setError(null);
    if (!globalThis.crypto?.randomUUID) {
      setError("This browser cannot create a secure request. Update the browser and try again.");
      return;
    }

    const fingerprint = JSON.stringify({
      student_id: selectedStudent.id,
      entry_mode: entryMode,
      delivery_mode: deliveryMode,
    });
    const key = intentRef.current?.fingerprint === fingerprint
      ? intentRef.current.key
      : globalThis.crypto.randomUUID();
    intentRef.current = { fingerprint, key };
    onPendingChange(true);

    try {
      const response = await create.mutateAsync({
        studentId: selectedStudent.id,
        mode: entryMode,
        delivery: deliveryMode,
        key,
      });
      intentRef.current = null;
      await queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListAssignedQueryKey() });
      onClose();
      router.push(`/portal/routine-interviews/${response.data.id}`);
    } catch (caught) {
      if (routineErrorCode(caught) === "idempotency_key_conflict") {
        intentRef.current = null;
      }
      setError(routineErrorMessage(
        caught,
        "The create response could not be confirmed. Retry with the same Student and visit details to safely check the result.",
      ));
    } finally {
      onPendingChange(false);
    }
  }

  return (
    <DialogContent
      className="max-w-2xl"
      onEscapeKeyDown={(event) => { if (pending) event.preventDefault(); }}
      onPointerDownOutside={(event) => { if (pending) event.preventDefault(); }}
    >
      <DialogTitle>Start direct Routine Interview</DialogTitle>
      <DialogDescription>
        Create a Counselor-assigned Routine Interview for a qualified Student. The Student will complete their Intake separately.
      </DialogDescription>

      {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
      {options.isPending ? (
        <div aria-busy="true" className="mt-5 space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : options.isError ? (
        <div role="alert" className="mt-5 border-y border-danger/30 py-4">
          <p className="text-sm text-danger">{routineErrorMessage(options.error, "Direct-creation options could not be loaded.")}</p>
          <Button className="mt-3" variant="secondary" onClick={() => void options.refetch()}>Retry</Button>
        </div>
      ) : deliveryModes.length === 0 ? (
        <p role="status" className="mt-5 border-y border-border py-4 text-sm text-muted">
          Direct Routine Interview creation is not configured for an available delivery mode.
        </p>
      ) : (
        <form className="mt-5 grid gap-5" onSubmit={(event) => void submit(event)}>
          <form
            className="grid gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              setCandidateSearch(studentSearch.trim());
              setCandidatePage(1);
            }}
          >
            <Label htmlFor="routine-direct-student-search">Find Student</Label>
            <Input
              id="routine-direct-student-search"
              type="search"
              value={studentSearch}
              onChange={(event) => setStudentSearch(event.target.value)}
              placeholder="Search by name or Institutional ID"
              autoComplete="off"
            />
            <Button type="submit" variant="secondary" className="justify-self-start">Search Students</Button>
          </form>

          <fieldset className="min-w-0">
            <legend className="mb-2 text-sm font-medium text-ink">Qualified Students</legend>
            {candidates.isPending ? (
              <div aria-busy="true" className="space-y-2">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : candidates.isError ? (
              <div role="alert" className="border-y border-danger/30 py-4">
                <p className="text-sm text-danger">{routineErrorMessage(candidates.error, "Student candidates could not be loaded.")}</p>
                <Button className="mt-3" variant="secondary" onClick={() => void candidates.refetch()}>Retry</Button>
              </div>
            ) : pageData?.items.length ? (
              <div className="divide-y divide-border rounded-md border border-border">
                {pageData.items.map((candidate) => (
                  <label key={candidate.id} className="flex cursor-pointer items-start gap-3 p-3 hover:bg-surface-muted/60">
                    <input
                      type="radio"
                      name="routine-student-candidate"
                      className="mt-1 size-4 accent-brand"
                      value={candidate.id}
                      checked={selectedStudent?.id === candidate.id}
                      onChange={() => changeStudent(candidate)}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block font-semibold text-ink">{candidate.display_name}</span>
                      <span className="mt-1 block text-xs text-muted">
                        {candidate.institutional_id ? `Institutional ID ${candidate.institutional_id} · ` : ""}
                        {candidate.inventory_context.academic_year.label} · {candidate.inventory_context.course}
                        {candidate.inventory_context.major.trim() ? ` · ${candidate.inventory_context.major}` : ""}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            ) : (
              <p className="border-y border-border py-4 text-sm text-muted">
                {candidateSearch ? "No qualified Students match this search." : "No qualified Student candidates are available."}
              </p>
            )}
            {pageData ? (
              <div className="mt-2 flex items-center justify-between gap-3">
                <p className="text-xs text-muted">Page {pageData.page}</p>
                <div className="flex gap-2">
                  <Button type="button" variant="secondary" className="min-h-8 px-3 py-1 text-xs" disabled={pageData.page <= 1 || candidates.isFetching} onClick={() => setCandidatePage((current) => Math.max(1, current - 1))}>Previous</Button>
                  <Button type="button" variant="secondary" className="min-h-8 px-3 py-1 text-xs" disabled={!pageData.has_next || candidates.isFetching} onClick={() => setCandidatePage((current) => current + 1)}>Next</Button>
                </div>
              </div>
            ) : null}
          </fieldset>

          {selectedStudent && !pageData?.items.some((candidate) => candidate.id === selectedStudent.id) ? (
            <p className="border-l-2 border-brand pl-3 text-sm text-ink">
              Selected Student: <span className="font-semibold">{selectedStudent.display_name}</span>
              {selectedStudent.institutional_id ? ` · ${selectedStudent.institutional_id}` : ""}
            </p>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="routine-direct-entry-mode">Nature of visit</Label>
              <select
                id="routine-direct-entry-mode"
                className={controlClass}
                value={entryMode}
                onChange={(event) => {
                  setEntryMode(event.target.value as DirectRoutineEntryMode | "");
                  intentRef.current = null;
                  setError(null);
                }}
                required
              >
                <option value="">Choose visit type</option>
                {entryModes.map((mode) => <option key={mode} value={mode}>{routineEntryModeLabel(mode)}</option>)}
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="routine-direct-delivery-mode">Delivery mode</Label>
              <select
                id="routine-direct-delivery-mode"
                className={controlClass}
                value={deliveryMode}
                onChange={(event) => {
                  setSelectedDeliveryMode(event.target.value as DeliveryMode | "");
                  intentRef.current = null;
                  setError(null);
                }}
                required
              >
                <option value="">Choose delivery mode</option>
                {deliveryModes.map((mode) => <option key={mode} value={mode}>{routineDeliveryModeLabel(mode)}</option>)}
              </select>
            </div>
          </div>

          <p className="text-sm text-muted">
            {options.data?.data.service.name} · {options.data?.data.service.code}
          </p>
          <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="secondary" disabled={pending} onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={pending || !selectedStudent || !entryMode || !deliveryMode} aria-busy={pending}>
              {pending ? "Creating…" : "Create Routine Interview"}
            </Button>
          </div>
        </form>
      )}
    </DialogContent>
  );
}
