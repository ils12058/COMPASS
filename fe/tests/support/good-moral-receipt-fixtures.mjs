import { certificate, counselor, requestId } from './good-moral-print-fixtures.mjs';
export { requestId };
export const revisionId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
export const nextRevisionId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
export const verificationId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
export const inspectorId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
export const version = '2026-10-24T01:00:00.000001+00:00';
export const nextVersion = '2026-10-24T01:01:00.000001+00:00';
export const inspector = { ...counselor, id: inspectorId, capabilities: [...counselor.capabilities, 'good_moral.prepare', 'good_moral.verify_receipt'] };
export const session = account => ({ user: account, session: { id: `session-${account.id}`, expires_at: '2099-01-01T00:00:00Z', is_current: true } });
export function receiptItem(status = 'NEEDS_VERIFICATION', mode = 'ACTIVE') {
  const verified = status === 'VERIFIED';
  const blocker = { MISSING: 'missing', INCOMPLETE: 'incomplete', NEEDS_VERIFICATION: 'unverified', LEGACY_CONFLICT: 'conflict', DISPUTED: 'conflict', POLICY_UNAVAILABLE: 'policy_unresolved' }[status];
  return { ...certificate('REQUESTED', 'GRADUATE'),
    initiation_origin: 'STUDENT_SELF', initiated_by: null,
    exit_interview_id: null, exit_interview_submitted_at: null, graduation_opportunity_id: null,
    prepared_by: null, prepared_at: null,
    official_receipt_number: status === 'MISSING' ? '' : 'OR-SYNTHETIC-000125', official_receipt_date: '2026-10-23', official_receipt_amount: '80.00',
    actions: { request_version: version, preparation_version: null, can_correct: true, can_prepare: mode === 'DORMANT' || verified, can_issue: false, can_cancel: true, can_download: false,
      correction_fields: ['degree', 'major', 'official_receipt_number', 'official_receipt_date', 'official_receipt_amount'] },
    receipt_identity: { ledger_mode: mode, revision_id: revisionId, identity_state: 'BOUND', history: [
      { id: revisionId, sequence: 1, change_kind: 'ASSIGNED', origin: 'ORDINARY', recorded_at: '2026-10-24T00:00:00Z', recorded_by_id: inspectorId, is_current: true, closed_at: null },
    ] },
    receipt_inspection: { status, blocker: mode === 'FENCED' ? 'good_moral_receipt_cutover_required' : mode === 'DORMANT' ? null : blocker ? `good_moral_receipt_${blocker}` : null,
      can_verify: mode === 'ACTIVE' && status === 'NEEDS_VERIFICATION',
      verification_id: verified ? verificationId : null, verified_by_id: verified ? inspectorId : null, verified_at: verified ? '2026-10-24T01:01:00Z' : null,
      method: verified ? 'PHYSICAL_OR_INSPECTION' : null, expected_amount: status === 'POLICY_UNAVAILABLE' || mode !== 'ACTIVE' ? null : '80.00', currency: status === 'POLICY_UNAVAILABLE' || mode !== 'ACTIVE' ? null : 'PHP' },
    receipt_mutation_result: null, receipt_verification_result: null,
  };
}
