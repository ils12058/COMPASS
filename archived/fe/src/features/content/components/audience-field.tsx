import type { ChangeEvent } from "react";

import { Label } from "@/components/ui/label";
import { AUDIENCE_OPTIONS } from "@/features/content/presentation";

export function AudienceField({
  id,
  value,
  onChange,
  disabled = false,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>Audience</Label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value)}
        className="min-h-10 w-full rounded-lg border bg-card px-3 py-2 text-sm"
      >
        <option value="">Choose who can read this</option>
        {AUDIENCE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {value === "PUBLIC" ? (
        <p className="text-xs leading-5 text-muted-foreground">
          Anyone can read this content on the public COMPASS site.
        </p>
      ) : null}
    </div>
  );
}
