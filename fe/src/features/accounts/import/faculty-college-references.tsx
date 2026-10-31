"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { useAccountsFacultyCollegeChoices } from "@/lib/api/generated/accounts/accounts";

export function FacultyCollegeReferences() {
  const [open, setOpen] = useState(false);
  const query = useAccountsFacultyCollegeChoices({ query: { enabled: open, retry: false } });
  return (
    <details className="mt-4 text-sm" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="min-h-11 cursor-pointer py-3 font-semibold text-brand">Faculty College references for CSV</summary>
      {open && query.isPending ? <p role="status">Loading College references…</p> : null}
      {open && query.isError ? <p role="alert">College references could not be loaded. <Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button></p> : null}
      {open && query.isSuccess ? query.data.data.length ? (
        <div className={dataTable.scroll}>
          <table className={dataTable.table}>
            <caption className="sr-only">Active Faculty home College references</caption>
            <thead className={dataTable.head}><tr>
              <th scope="col" className={dataTable.headerCell}>Campus / College</th>
              <th scope="col" className={dataTable.headerCell}>faculty_college_id</th>
            </tr></thead>
            <tbody className={dataTable.body}>{query.data.data.map((college) => <tr key={college.id} className={dataTable.row}>
              <td className={dataTable.cell}>{college.campus_code} · {college.name}</td>
              <td className={`${dataTable.cell} select-all break-all`}>{college.id}</td>
            </tr>)}</tbody>
          </table>
        </div>
      ) : <p>No active Colleges are available.</p> : null}
    </details>
  );
}
