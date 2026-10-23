// Per-view cancellation barrier, not reusable authorization or a second server-state store.
export class CoverageGeneration {
    private value = 0;
    invalidate() { this.value += 1; }
    current() { return this.value; }
    assertCurrent(captured: number, signal?: AbortSignal) {
        if (captured !== this.value || signal?.aborted)
            throw new Error("Coverage access needs to be checked again.");
    }
}
export const evaluationLabels = {
    academic_adjustment_rating: "Academic adjustment",
    physical_adjustment_rating: "Physical adjustment",
    social_adjustment_rating: "Social adjustment",
    spiritual_adjustment_rating: "Spiritual adjustment",
    financial_adjustment_rating: "Financial adjustment",
    emotional_adjustment_rating: "Emotional adjustment",
    other_adjustment: "Other adjustment",
    special_concern: "Special concern",
    recommendations: "Recommendations",
} as const;
export function presentApprovedEvaluation(values: Partial<Record<keyof typeof evaluationLabels, string | number | null>>) {
    return Object.entries(evaluationLabels).flatMap(([key, label]) => {
        if (!Object.hasOwn(values, key))
            return [];
        const value = values[key as keyof typeof evaluationLabels];
        return [{ key, label, value: value === null ? "Not rated" : value === "" ? "No text recorded" : String(value) }];
    });
}
