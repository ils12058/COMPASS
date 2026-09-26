// ADR-060 reserves this stable code for the canonical Counseling Service. It identifies
// Counseling Appointments; system-required Service policy comes from `is_system_required`.
export const CANONICAL_COUNSELING_SERVICE_CODE = "COUNSELING";

export function isCounselingService(service: { code: string }): boolean {
  return service.code === CANONICAL_COUNSELING_SERVICE_CODE;
}
