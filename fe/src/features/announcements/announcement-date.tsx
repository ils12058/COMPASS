import { formatPublicDate, publicDateParts } from "@/features/public/shared/presentation";

// A calendar-style date read at a glance; screen readers hear the full date once.
export function AnnouncementDate({ value }: { value: string }) {
  const parts = publicDateParts(value);

  return (
    <time
      dateTime={value}
      className="flex flex-col items-center rounded-sm border border-brand-line bg-brand-wash py-1.5 text-center"
    >
      {parts ? (
        <>
          <span className="sr-only">{formatPublicDate(value)}</span>
          <span aria-hidden="true" className="text-xs font-bold uppercase leading-4 tracking-[0.12em] text-brand">
            {parts.month}
          </span>
          <span aria-hidden="true" className="font-heading text-2xl font-bold leading-7 text-ink">
            {parts.day}
          </span>
          <span aria-hidden="true" className="text-xs leading-4 text-muted">
            {parts.year}
          </span>
        </>
      ) : (
        <span className="px-1 text-xs text-muted">{formatPublicDate(value)}</span>
      )}
    </time>
  );
}
