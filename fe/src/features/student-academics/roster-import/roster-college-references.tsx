"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import {
  useOrganizationListCampuses,
  useOrganizationListColleges,
} from "@/lib/api/generated/organization/organization";

export function RosterCollegeReferences() {
  const [open, setOpen] = useState(false);
  const campuses = useOrganizationListCampuses(
    { is_active: true },
    { query: { enabled: open, retry: false } },
  );
  const colleges = useOrganizationListColleges(
    { is_active: true },
    { query: { enabled: open, retry: false } },
  );
  const failed = campuses.isError || colleges.isError;

  return (
    <details className="mt-4 text-sm" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="min-h-11 cursor-pointer py-3 font-semibold text-brand">
        Active campus and College codes
      </summary>
      {open && (campuses.isPending || colleges.isPending) ? (
        <p role="status">Loading campus and College references…</p>
      ) : null}
      {open && failed ? (
        <p role="alert">
          Campus and College references could not be loaded.{" "}
          <Button
            variant="secondary"
            onClick={() => {
              void campuses.refetch();
              void colleges.refetch();
            }}
          >
            Retry
          </Button>
        </p>
      ) : null}
      {open && !failed && campuses.isSuccess && colleges.isSuccess ? (
        colleges.data.data.items.filter(
          (college) => college.is_active && college.campus.is_active,
        ).length ? (
          <div className={dataTable.scroll}>
            <table className={dataTable.table}>
              <caption className="sr-only">
                Active catalog campus and College codes for academic roster import
              </caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={dataTable.headerCell}>
                    campus_code
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    college_code
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    College
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Campus
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {colleges.data.data.items
                  .filter((college) => college.is_active && college.campus.is_active)
                  .map((college) => (
                    <tr key={college.id} className={dataTable.row}>
                      <td className={dataTable.cell}>{college.campus.code}</td>
                      <td className={dataTable.cell}>{college.code}</td>
                      <td className={dataTable.cell}>{college.name}</td>
                      <td className={dataTable.cell}>{college.campus.name}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No active Colleges are available.</p>
        )
      ) : null}
    </details>
  );
}
