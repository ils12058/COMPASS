"use client";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useAccountsFacultyCollegeChoices } from "@/lib/api/generated/accounts/accounts";

export function FacultyCollegeField({ id, value, onChange, disabled = false }: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const choices = useAccountsFacultyCollegeChoices({ query: { retry: false, refetchOnMount: "always" } });
  const options = choices.isError ? [] : choices.data?.data ?? [];
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>Faculty home College</Label>
      <Select id={id} value={value} disabled={disabled || choices.isPending || choices.isError}
        onChange={(event) => onChange(event.target.value)} aria-describedby={`${id}-help`}>
        <option value="">Not assigned</option>
        {value && !options.some((college) => college.id === value) ? <option value={value} disabled>Current selection unavailable</option> : null}
        {options.map((college) => <option key={college.id} value={college.id}>{college.campus_code} · {college.name}</option>)}
      </Select>
      <p id={`${id}-help`} className="text-sm text-muted">Institutional home only. Digital Referrals are not available.</p>
      {choices.isPending ? <p role="status" className="text-sm text-muted">Loading Colleges…</p> : null}
      {choices.isError ? <p role="alert" className="text-sm text-danger">Colleges could not be loaded. <Button variant="quiet" onClick={() => void choices.refetch()}>Retry</Button></p> : null}
    </div>
  );
}
