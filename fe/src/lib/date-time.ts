import {
  formatDateOnly,
  formatInstitutionalDateTime,
  institutionalDateInputValue,
  institutionalDateTimeInputToISO,
  isFutureInstitutionalDateInput,
  isFutureInstitutionalDateTimeInput,
  isoToInstitutionalDateTimeInput,
} from "./institutional-time";

export {
  formatDateOnly,
  formatDateTimeInZone,
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE,
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateInputValue,
  institutionalDateTimeInputToISO,
  institutionalDateTimeInputValue,
  isFutureInstitutionalDateInput,
  isFutureInstitutionalDateTimeInput,
  isoToInstitutionalDateTimeInput,
} from "./institutional-time";

/** @deprecated Prefer institutionalDateTimeInputToISO for explicit semantics. */
export const dateTimeInputToISO = institutionalDateTimeInputToISO;

/** @deprecated Prefer isoToInstitutionalDateTimeInput for explicit semantics. */
export const isoToDateTimeInput = isoToInstitutionalDateTimeInput;

/** @deprecated Prefer institutionalDateInputValue for explicit semantics. */
export const localDateInputValue = institutionalDateInputValue;

/** @deprecated Prefer isFutureInstitutionalDateInput for explicit semantics. */
export const isFutureDateInput = isFutureInstitutionalDateInput;

/** @deprecated Prefer isFutureInstitutionalDateTimeInput for explicit semantics. */
export const isFutureDateTimeInput = isFutureInstitutionalDateTimeInput;

/** @deprecated Prefer formatInstitutionalDateTime for explicit semantics. */
export const formatDateTime = formatInstitutionalDateTime;
