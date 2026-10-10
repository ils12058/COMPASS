"use client";

import { dataTable } from "@/components/ui/data-table";
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
    // Sits flush inside the selected family's Panel, which draws the frame.
    <div className={`min-w-0 ${dataTable.scroll}`}>
      <table className={`${dataTable.table} min-w-[36rem]`}>
        <caption className="sr-only">
          Form Revisions for {familyTitle}
        </caption>
        <thead className={dataTable.head}>
          <tr>
            <th scope="col" className={dataTable.headerCell}>Official code</th>
            <th scope="col" className={dataTable.headerCell}>Official revision</th>
            <th scope="col" className={dataTable.headerCell}>Status</th>
            <th scope="col" className={dataTable.headerCell}>COMPASS support</th>
          </tr>
        </thead>
        <tbody className={dataTable.body}>
          {revisions.map((revision) => (
            <tr key={revision.id} className={dataTable.row}>
              <td className={`${dataTable.cell} font-mono text-xs text-ink`}>
                {revision.official_code ?? "Not recorded"}
              </td>
              <td className={`${dataTable.cell} text-ink`}>
                {revision.official_revision ?? "Not recorded"}
              </td>
              <td className={dataTable.cell}>
                <FormRevisionStatusBadge status={revision.status} />
              </td>
              <td className={dataTable.cell}>
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
