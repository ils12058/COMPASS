"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { GoodMoralAssistedAcademicContextResponse } from "@/lib/api/generated/model";

// Read-only preview of the academic details the backend will prefill for an assisted current
// Student request. Only values that exist in the Student's records are shown; missing fields stay
// blank rather than guessed. They remain editable later through Correct certificate details.
export function AssistedAcademicPrefill({ context }: { context?: GoodMoralAssistedAcademicContextResponse | null }) {
  return <>
    <div><Label htmlFor="assisted-college">College</Label><Input id="assisted-college" className="mt-2" value={context?.college ?? ""} readOnly placeholder="Not recorded" /></div>
    <div><Label htmlFor="assisted-course">Course / Program</Label><Input id="assisted-course" className="mt-2" value={context?.course ?? ""} readOnly placeholder="Not recorded" /></div>
    <div><Label htmlFor="assisted-major-current">Major</Label><Input id="assisted-major-current" className="mt-2" value={context?.major ?? ""} readOnly placeholder="Not recorded" /></div>
    <div><Label htmlFor="assisted-academic-year">Academic Year</Label><Input id="assisted-academic-year" className="mt-2" value={context?.academic_year ?? ""} readOnly placeholder="Not recorded" /></div>
    <p className="text-xs text-muted sm:col-span-2">Prefilled from the Student&apos;s submitted Inventory and current placement. Fields left blank were not found in the records; you can correct them after the request is created.</p>
  </>;
}