const pdfPrefixes = {
  individualInventory: "individual-inventory",
  exitInterview: "exit-interview",
  goodMoral: "good-moral",
  referralSlip: "referral-slip",
  callSlip: "call-slip",
} as const;

export function institutionalPdfFallbackFilename(
  kind: keyof typeof pdfPrefixes,
  recordId: string,
): string {
  return `${pdfPrefixes[kind]}-${recordId}.pdf`;
}

export function studentProfilingPdfFallbackFilename(academicYearLabel: string): string {
  const safeYear = academicYearLabel.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^[-._]+|[-._]+$/g, "") || "academic-year";
  return `student-profile-${safeYear}.pdf`;
}
