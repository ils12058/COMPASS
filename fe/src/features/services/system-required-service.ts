// ADR-060: COMPASS provisions the COUNSELING Service for Counseling, Routine
// Interview, and E-Counseling workflows. It must stay active and keep Counselor
// eligibility. ServiceResponse has no flag for this, so the reserved code
// identifies it.
export const COUNSELING_SERVICE_CODE = "COUNSELING";

export function isSystemRequiredService(service: { code: string }): boolean {
  return service.code === COUNSELING_SERVICE_CODE;
}
