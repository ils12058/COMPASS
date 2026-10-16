import { user } from './ui-hierarchy-fixtures.mjs';
export const requestId = '11111111-1111-4111-8111-111111111116';
export const preparedVersion = '2026-10-15T00:00:00.123456+00:00';
export const counselor = { ...user(), capabilities: [...user().capabilities, 'good_moral.view', 'good_moral.manage', 'good_moral.issue'] };
export function certificate(status = 'READY_FOR_ISSUANCE', variant = 'CURRENT_STUDENT') {
  const issued = status === 'ISSUED';
  return {
    id: requestId, variant, status, applicant_name: 'Synthetic Applicant',
    student: { id: 'student', display_name: 'Synthetic Student' }, student_institutional_id: 'SYNTHETIC-16',
    inventory_id: variant === 'CURRENT_STUDENT' ? 'inventory' : null, academic_year: { id: 'year', label: '2026-2027' },
    year_level: '4th Year', course: 'BS Computing', college: 'College of Computing', semester: 'First Semester', major: 'Software',
    degree: 'BS Computing', graduation_date: '2026-06-01', official_receipt_number: 'SYNTHETIC-OR', official_receipt_date: '2026-10-15', official_receipt_amount: '100.00',
    form_revision: issued ? { id: 'revision', family_key: variant === 'CURRENT_STUDENT' ? 'good_moral_current_student' : 'good_moral_graduate', internal_schema_version: 1, official_code: variant === 'CURRENT_STUDENT' ? 'UCN-OP-GCO-01F4' : 'UCN-OP-GCO-01F6', official_revision: '1' } : null,
    document_template_key: issued ? variant === 'CURRENT_STUDENT' ? 'good_moral_current_student' : 'good_moral_graduate' : null,
    document_template_version: issued ? 2 : null,
    prepared_by: { id: 'staff', display_name: 'Synthetic Staff' }, prepared_at: preparedVersion,
    issued_by: issued ? { id: 'counselor', display_name: 'Current Counselor Name' } : null,
    issued_by_name_snapshot: issued ? 'Frozen Issuer Name' : '', issued_at: issued ? '2026-10-16T00:00:00Z' : null,
    created_at: '2026-10-15T00:00:00Z', updated_at: '2026-10-16T00:00:00Z', cancelled_at: null, cancellation: null,
    actions: { request_version: '2026-10-16T00:00:00.000000+00:00', preparation_version: preparedVersion, can_correct: false, can_prepare: false, can_issue: status === 'READY_FOR_ISSUANCE', can_cancel: status === 'READY_FOR_ISSUANCE', can_download: issued, correction_fields: [] },
  };
}
// A small valid PDF for native viewer/download tests. This fixture is not an official template.
const objects = [
  '<< /Type /Catalog /Pages 2 0 R >>',
  '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
  '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
  '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
];
const stream = 'BT /F1 18 Tf 50 780 Td (SYNTHETIC finalized certificate PDF) Tj ET\n';
objects.push(`<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}endstream`);
let pdf = '%PDF-1.4\n';
const offsets = [0];
for (const [index, object] of objects.entries()) { offsets.push(Buffer.byteLength(pdf)); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; }
const xref = Buffer.byteLength(pdf);
pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(n => `${String(n).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
export const pdfBytes = Buffer.from(pdf);
