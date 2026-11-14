import type { ReferralSchedulingStatementResponse, ReferralSchedulingVerificationResponse, ReferralTimingWindowResponse } from "@/lib/api/generated/model";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";
import { formatTimingWindowTime, reportedProvenance } from "./timing-presentation";

const weekdays = { MONDAY: "Monday", TUESDAY: "Tuesday", WEDNESDAY: "Wednesday", THURSDAY: "Thursday", FRIDAY: "Friday", SATURDAY: "Saturday" };
export const confirmationSourceLabels = { STUDENT_CONFIRMED: "Student confirmed", REFERRER_CONFIRMED: "Referrer confirmed", OFFICE_RECORD: "Office record" };

export function TimingWindows({ windows }: { windows: ReferralTimingWindowResponse[] }) {
  return <ul className="space-y-2 text-sm">
    {windows.map((window, index) => <li key={index} className="[overflow-wrap:anywhere]">
      <p className="font-medium">{window.information_type === "STUDENT_AVAILABLE" ? "The student is usually free" : "The student may leave the referrer’s class"}</p>
      <p>{window.pattern === "SPECIFIC_DATE" ? formatDateOnly(window.date) : window.weekday ? `${weekdays[window.weekday]} · valid until ${formatDateOnly(window.valid_until)}` : "Weekday not recorded"} · {formatTimingWindowTime(window.start_time)}–{formatTimingWindowTime(window.end_time)} · Philippine Time</p>
      {window.expired ? <p className="font-medium text-warning">{window.pattern === "SPECIFIC_DATE" ? "This time has passed" : `No longer valid after ${formatDateOnly(window.valid_until)}`}</p> : null}
    </li>)}
  </ul>;
}

export function ReportedTiming({ statement, headingId = "reported-referral-timing" }: { statement?: ReferralSchedulingStatementResponse | null; headingId?: string }) {
  return <section aria-labelledby={headingId} className="min-w-0 space-y-2">
    <h3 id={headingId} className="text-sm font-semibold text-brand">Reported by the referrer</h3>
    {statement ? <>
      <p className="text-sm text-muted [overflow-wrap:anywhere]">{reportedProvenance(statement)}</p>
      {statement.answer_kind === "UNKNOWN" ? <p className="text-sm">Unknown / needs confirmation</p> : <TimingWindows windows={statement.windows} />}
      {statement.note ? <p className="whitespace-pre-wrap text-sm [overflow-wrap:anywhere]"><span className="font-semibold">Scheduling constraints: </span>{statement.note}</p> : null}
    </> : <p className="text-sm text-muted">Timing: Not provided. Timing information was not asked for on this Referral.</p>}
  </section>;
}

function Verification({ record }: { record: ReferralSchedulingVerificationResponse }) {
  return <div className="min-w-0 space-y-2">
    <p className="text-sm font-semibold">{confirmationSourceLabels[record.confirmation_source]}</p>
    <p className="text-sm text-muted [overflow-wrap:anywhere]">Recorded by {record.author_name} on {formatInstitutionalDateTime(record.created_at)} · Philippine Time</p>
    {record.answer_kind === "NO_SUITABLE_TIME" ? <p className="text-sm">No suitable time confirmed</p> : <TimingWindows windows={record.windows} />}
    {record.note ? <p className="whitespace-pre-wrap text-sm [overflow-wrap:anywhere]"><span className="font-semibold">Scheduling constraints: </span>{record.note}</p> : null}
  </div>;
}

export function VerifiedTiming({ records, headingId = "verified-referral-timing" }: { records: ReferralSchedulingVerificationResponse[]; headingId?: string }) {
  const latest = records[0];
  return <section aria-labelledby={headingId} className="min-w-0 space-y-2">
    <h3 id={headingId} className="text-sm font-semibold text-brand">Verified availability</h3>
    {latest ? <Verification record={latest} /> : <p className="text-sm text-muted">No staff verification recorded.</p>}
    {records.length > 1 ? <div className="border-t border-border pt-3">
      <h4 className="text-sm font-semibold">Earlier verifications</h4>
      <ol className="mt-2 space-y-3">{records.slice(1).map(record => <li key={record.id}><Verification record={record} /></li>)}</ol>
    </div> : null}
  </section>;
}
