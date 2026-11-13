import { PersonAvatar } from "@/features/account/components/person-avatar";
import { CounselorAboutButton } from "@/features/counselor-about/counselor-about-dialog";
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

// About sits beside each choice, never inside its label, so opening it cannot select a Counselor.
export function BookingCounselorChoice({ items, value, onChange, disabled = false }: {
  items: EligibleCounselorResponse[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}) {
  if (items.length === 1) {
    return (
      <div className="@container flex flex-wrap items-center gap-3">
        <CounselorIdentity counselor={items[0]} />
        <CounselorAboutButton counselorId={items[0].id} counselorName={items[0].display_name} />
      </div>
    );
  }
  return (
    <fieldset disabled={disabled} className="@container min-w-0">
      <legend className="sr-only">Counselor</legend>
      <div className="grid gap-2 @min-[40rem]:grid-cols-2">
        {items.map((counselor) => (
          <div key={counselor.id} className="flex min-w-0 items-center gap-1 rounded-md border border-border-strong pr-1 has-[input:checked]:border-brand has-[input:checked]:bg-brand-wash has-[input:focus]:ring-2 has-[input:focus]:ring-focus has-[input:focus]:ring-offset-2">
            <label className="flex min-w-0 flex-1 cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
              <input type="radio" name="booking-counselor" value={counselor.id} checked={value === counselor.id} onChange={() => onChange(counselor.id)} className="size-4 shrink-0 accent-brand" />
              <CounselorIdentity counselor={counselor} />
            </label>
            <CounselorAboutButton counselorId={counselor.id} counselorName={counselor.display_name} />
          </div>
        ))}
      </div>
    </fieldset>
  );
}
