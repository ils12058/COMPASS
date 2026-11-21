import { Label } from "@/components/ui/label";

export const urgencyHelp = "Mark this if the student needs attention today. If someone is in immediate danger, contact the Guidance and Counseling Office or campus security directly. COMPASS is not an emergency hotline.";

export function UrgentBadge({ urgent }: { urgent?: boolean }) {
  return urgent ? <span className="inline-block rounded-sm bg-danger/10 px-2 py-1 text-sm font-semibold text-danger">Urgent</span> : null;
}

export function UrgencyCheckbox({ id, checked, onChange, disabled = false }: { id: string; checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean }) {
  return <div className="space-y-2">
    <div className="flex min-h-11 items-center gap-3">
      <input id={id} name="is_urgent" type="checkbox" className="h-4 w-4 shrink-0 accent-brand" checked={checked} disabled={disabled} aria-describedby={`${id}-help`} onChange={event => onChange(event.target.checked)} />
      <Label htmlFor={id}>This concern is urgent</Label>
    </div>
    <p id={`${id}-help`} className="text-sm leading-6 text-muted">{urgencyHelp}</p>
  </div>;
}

export function UrgentFilter({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return <div className="flex min-h-11 items-center gap-3">
    <input id="referrals-urgent" type="checkbox" className="h-4 w-4 accent-brand" checked={checked} onChange={event => onChange(event.target.checked)} />
    <Label htmlFor="referrals-urgent">Urgent only</Label>
  </div>;
}
