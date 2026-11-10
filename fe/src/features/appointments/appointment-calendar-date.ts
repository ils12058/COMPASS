// DayPicker uses Date objects for civil calendar math. Pin that representation to UTC;
// it is never an appointment instant. Only backend-returned slots carry instants.
export function calendarDate(value: string): Date | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000-")) return undefined;
  const date = new Date(`${value}T12:00:00Z`);
  return !Number.isNaN(date.getTime()) && calendarDateValue(date) === value ? date : undefined;
}

export function calendarDateValue(date: Date): string {
  return `${String(date.getUTCFullYear()).padStart(4, "0")}-${String(date.getUTCMonth() + 1).padStart(2, "0")}-${String(date.getUTCDate()).padStart(2, "0")}`;
}
