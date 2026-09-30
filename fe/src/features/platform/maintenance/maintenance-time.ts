import {
  formatInstitutionalDateTime,
  institutionalDateTimeInputToISO,
  institutionalDateTimeInputValue,
  isoToInstitutionalDateTimeInput,
} from "../../../lib/institutional-time";

export function toLocalDateTimeValue(value: string | null): string {
  return isoToInstitutionalDateTimeInput(value);
}

export function localDateTimeToIso(value: string): string | null {
  return institutionalDateTimeInputToISO(value);
}

export function formatLocalDateTime(value: string): string {
  const formatted = formatInstitutionalDateTime(value);
  return formatted === value ? "the selected time" : formatted;
}

export function currentLocalDateTimeValue(): string {
  return institutionalDateTimeInputValue();
}
