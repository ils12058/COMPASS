"use client";

import { useId, useState } from "react";
import { DayPicker } from "react-day-picker";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { formatDateOnly, institutionalDateInputValue } from "@/lib/institutional-time";
import { calendarDate, calendarDateValue } from "./appointment-calendar-date";

const months = Array.from({ length: 12 }, (_, month) =>
  new Intl.DateTimeFormat("en", { month: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2000, month, 1))),
);
const focusStyle = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1";

export function AppointmentDateCalendar({
  value, onChange, label = "Appointment date", min, disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  min: string;
  disabled?: boolean;
}) {
  const id = useId();
  const today = calendarDate(institutionalDateInputValue());
  const selected = calendarDate(value);
  const earliest = calendarDate(min);
  const [month, setMonth] = useState(() => selected ?? earliest ?? today!);
  const [yearDraft, setYearDraft] = useState(String(month.getUTCFullYear()));
  const [yearError, setYearError] = useState(false);
  const monthKey = calendarDateValue(month).slice(0, 7);
  const minMonth = min.slice(0, 7);

  function navigate(next: Date) {
    const bounded = earliest && calendarDateValue(next).slice(0, 7) < minMonth ? earliest : next;
    setMonth(bounded);
    setYearDraft(String(bounded.getUTCFullYear()));
    setYearError(false);
  }

  function jumpYear() {
    const next = calendarDate(`${yearDraft}-${String(month.getUTCMonth() + 1).padStart(2, "0")}-01`);
    if (!next || yearDraft === "0000" || (earliest && next.getUTCFullYear() < earliest.getUTCFullYear())) {
      setYearError(true);
      return;
    }
    navigate(next);
  }

  function shiftMonth(offset: number) {
    const next = new Date(month);
    next.setUTCDate(1);
    next.setUTCMonth(next.getUTCMonth() + offset);
    navigate(next);
  }

  return (
    <fieldset disabled={disabled} aria-describedby={`${id}-help`} className="min-w-0 w-full max-w-sm">
      <legend className="mb-2 text-sm font-semibold text-ink">{label}</legend>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-0 flex-1 basis-28">
          <Label htmlFor={`${id}-month`} className="text-xs">Month</Label>
          <div className="relative">
          <Select className="min-h-11 appearance-none pr-9" id={`${id}-month`} value={month.getUTCMonth()} onChange={(event) => {
            const next = new Date(month);
            next.setUTCDate(1);
            next.setUTCMonth(Number(event.target.value));
            navigate(next);
          }}>
            {months.map((name, index) => <option key={name} value={index} disabled={month.getUTCFullYear() === earliest?.getUTCFullYear() && index < earliest.getUTCMonth()}>{name}</option>)}
          </Select>
          <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          </div>
        </div>
        <div className="w-20 max-w-full">
          <Label htmlFor={`${id}-year`} className="text-xs">Year</Label>
          <Input id={`${id}-year`} inputMode="numeric" maxLength={4} value={yearDraft}
            aria-invalid={yearError || undefined} aria-describedby={yearError ? `${id}-error` : undefined}
            onChange={(event) => { setYearDraft(event.target.value); setYearError(false); }}
            onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); jumpYear(); } }} />
        </div>
        <Button variant="secondary" onClick={jumpYear}>Go</Button>
      </div>
      {yearError ? <p id={`${id}-error`} role="alert" className="mt-2 text-sm text-danger">Enter a four-digit year from {earliest?.getUTCFullYear() ?? 1} to 9999.</p> : null}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <Button className="px-2" variant="secondary" aria-label="Previous month" disabled={disabled || monthKey <= minMonth} onClick={() => shiftMonth(-1)}><ChevronLeft aria-hidden="true" className="size-4" /></Button>
        <p aria-live="polite" aria-atomic="true" className="min-w-0 flex-1 text-center font-heading font-semibold text-ink">{months[month.getUTCMonth()]} {month.getUTCFullYear()}</p>
        <Button className="px-2" variant="secondary" aria-label="Next month" disabled={disabled || monthKey === "9999-12"} onClick={() => shiftMonth(1)}><ChevronRight aria-hidden="true" className="size-4" /></Button>
      </div>
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`${label} calendar days`}>
      <DayPicker
        mode="single" required timeZone="UTC" weekStartsOn={0}
        month={month} onMonthChange={navigate} selected={selected} today={today}
        startMonth={earliest} endMonth={calendarDate("9999-12-31")}
        disabled={disabled ? true : earliest ? { before: earliest } : undefined}
        onSelect={(day) => { if (day) onChange(calendarDateValue(day)); }}
        hideNavigation
        aria-label={label}
        formatters={{ formatWeekdayName: (day) => new Intl.DateTimeFormat("en", { weekday: "short", timeZone: "UTC" }).format(day).slice(0, 2) }}
        classNames={{
          root: "mt-2",
          month_caption: "sr-only",
          month_grid: "w-full min-w-56 table-fixed border-collapse",
          weekday: "h-8 text-center text-xs font-medium text-muted",
          day: "p-0.5 text-center [&[data-selected]>button]:border-brand [&[data-selected]>button]:bg-brand [&[data-selected]>button]:text-on-brand",
          day_button: `w-full min-h-11 rounded-md border border-transparent text-sm font-medium text-ink hover:bg-surface-subtle disabled:text-muted disabled:opacity-50 ${focusStyle}`,
          today: "[&>button]:border-brand [&>button]:font-bold [&>button]:underline [&>button]:decoration-2 [&>button]:underline-offset-4",
          hidden: "invisible",
        }}
      />
      </div>
      <p className="mt-2 text-sm text-ink" role="status">{value ? `Selected date: ${formatDateOnly(value, { dateStyle: "long" })}` : "No date selected."}</p>
      <p id={`${id}-help`} className="mt-1 text-xs leading-5 text-muted">Use arrow keys to move by day, Page Up/Down by month, and Enter to select. Today is underlined.</p>
      <Button variant="quiet" className="mt-1" onClick={() => navigate(today!)}>Go to today</Button>
    </fieldset>
  );
}
