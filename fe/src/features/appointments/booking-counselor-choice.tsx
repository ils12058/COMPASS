import { PersonAvatar } from "@/features/account/components/person-avatar";
import type { EligibleCounselorResponse } from "@/lib/api/generated/model";

function CounselorIdentity({ counselor }: { counselor: EligibleCounselorResponse }) {
  return <>
    <PersonAvatar displayName={counselor.display_name} photoUrl={counselor.profile_photo_url} photoUpdatedAt={counselor.profile_photo_updated_at} />
    <span className="min-w-0 flex-1 basis-full text-sm leading-6 [overflow-wrap:anywhere] @min-[20rem]:basis-auto">
      <span className="block font-semibold text-ink">{counselor.display_name}</span>
      {counselor.is_default ? <span className="block text-xs text-muted">Assigned to you</span> : null}
    </span>
  </>;
}

export function BookingCounselorChoice({ items, value, onChange, disabled = false }: {
  items: EligibleCounselorResponse[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}) {
  if (items.length === 1) return <div className="@container flex flex-wrap items-center gap-3"><CounselorIdentity counselor={items[0]} /></div>;
  return (
    <fieldset disabled={disabled} className="@container min-w-0">
      <legend className="sr-only">Counselor</legend>
      <div className="grid gap-2 @min-[40rem]:grid-cols-2">
        {items.map((counselor) => (
          <label key={counselor.id} className="flex min-w-0 cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-border-strong px-3 py-2 has-[:checked]:border-brand has-[:checked]:bg-brand-wash has-[:focus]:ring-2 has-[:focus]:ring-focus has-[:focus]:ring-offset-2">
            <input type="radio" name="booking-counselor" value={counselor.id} checked={value === counselor.id} onChange={() => onChange(counselor.id)} className="size-4 shrink-0 accent-brand" />
            <CounselorIdentity counselor={counselor} />
          </label>
        ))}
      </div>
    </fieldset>
  );
}
