"use client";

import { FormRevisionStatusBadge } from "@/features/institution-configuration/institution-shared";
import type { FormRevisionResponse } from "@/lib/api/generated/model";

export function FormRevisionList({
  familyTitle,
  revisions,
}: {
  familyTitle: string;
  revisions: FormRevisionResponse[];
}) {
  return (
    <div className="min-w-0 overflow-x-auto rounded-sm border border-border">
      <table className="w-full min-w-[36rem] text-left text-sm">
        <caption className="sr-only">
          Form Revisions for {familyTitle}
        </caption>
        <thead className="border-b border-border bg-surface-muted text-xs font-semibold text-muted">
          <tr>
            <th scope="col" className="px-4 py-3">Official code</th>
            <th scope="col" className="px-4 py-3">Official revision</th>
            <th scope="col" className="px-4 py-3">Status</th>
            <th scope="col" className="px-4 py-3">COMPASS support</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {revisions.map((revision) => (
            <tr key={revision.id}>
              <td className="px-4 py-3 font-mono text-xs text-ink">
                {revision.official_code ?? "Not recorded"}
              </td>
              <td className="px-4 py-3 text-ink">
                {revision.official_revision ?? "Not recorded"}
              </td>
              <td className="px-4 py-3">
                <FormRevisionStatusBadge status={revision.status} />
              </td>
              <td className="px-4 py-3">
                {revision.supported ? (
                  <span className="font-semibold text-success">Supported</span>
                ) : (
                  <span className="text-danger">Unsupported by this COMPASS version</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
