"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { FilePlus2, Settings2 } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import {
  FloatingListTools,
  ListSearchField,
} from "@/components/ui/floating-list-tools";
import { Input } from "@/components/ui/input";
import { PageActionGroup, PageActionLink } from "@/components/ui/page-action";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { describeResultPage } from "@/features/portal/components/result-context";
import {
  useAssessmentRecordsList,
  useAssessmentRecordsListTypes,
} from "@/lib/api/generated/assessment-records/assessment-records";
import { AssessmentRecordOrdering } from "@/lib/api/generated/model";
import { formatDateOnly } from "@/lib/institutional-time";
import { getAssessmentRecordsAccess } from "./assessment-records-access";
import {
  assessmentErrorMessage,
  AssessmentLoading,
} from "./assessment-records-shared";

export const assessmentOrderLabels: Record<AssessmentRecordOrdering, string> = {
  NEWEST_ADMINISTERED: "Newest administered",
  OLDEST_ADMINISTERED: "Oldest administered",
  RECENTLY_UPDATED: "Recently updated",
  STUDENT_ASC: "Student A–Z",
  STUDENT_DESC: "Student Z–A",
};

export function AssessmentListPage() {
  const { user } = usePortalSession();
  const access = getAssessmentRecordsAccess(user);
  const router = useRouter();
  const params = useSearchParams();
  const applied = params.toString();
  const order =
    Object.values(AssessmentRecordOrdering).find(
      (value) => value === params.get("ordering"),
    ) ?? AssessmentRecordOrdering.NEWEST_ADMINISTERED;
  const page = Math.max(1, Number.parseInt(params.get("page") ?? "1", 10) || 1);
  const current = {
    search: params.get("search") ?? "",
    type: params.get("assessment_type_id") ?? "",
    from: params.get("administered_from") ?? "",
    to: params.get("administered_to") ?? "",
    ordering: order,
  };
  const [form, setForm] = useState({ applied, values: current });
  if (form.applied !== applied) setForm({ applied, values: current });
  const draft = form.values;
  const rangeInvalid = Boolean(draft.from && draft.to && draft.from > draft.to);
  const list = useAssessmentRecordsList(
    {
      search: current.search || undefined,
      assessment_type_id: current.type || undefined,
      administered_from: current.from || undefined,
      administered_to: current.to || undefined,
      student_id: params.get("student_id") || undefined,
      ordering: order,
      page,
      page_size: 20,
    },
    { query: { enabled: access.canView, retry: false } },
  );
  const types = useAssessmentRecordsListTypes(undefined, {
    query: { enabled: access.canView, retry: false },
  });
  const data = safeQueryData(list)?.data;
  const typeData = safeQueryData(types)?.data;
  const filtered = Boolean(
    current.search ||
      current.type ||
      current.from ||
      current.to ||
      params.get("student_id"),
  );
  const filterCount = [
    current.type,
    current.from,
    current.to,
    order !== "NEWEST_ADMINISTERED",
    params.get("student_id"),
  ].filter(Boolean).length;
  function field(name: keyof typeof draft, value: string) {
    if (name === "ordering") {
      const next = Object.values(AssessmentRecordOrdering).find(
        (item) => item === value,
      );
      if (next) setForm({ applied, values: { ...draft, ordering: next } });
    } else setForm({ applied, values: { ...draft, [name]: value } });
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (rangeInvalid) return;
    const next = new URLSearchParams();
    for (const [key, value] of [
      ["search", draft.search.trim()],
      ["assessment_type_id", draft.type],
      ["administered_from", draft.from],
      ["administered_to", draft.to],
      ["ordering", draft.ordering],
      ["student_id", params.get("student_id") ?? ""],
    ])
      if (value) next.set(key, value);
    router.push("/portal/assessment-records?" + next.toString(), {
      scroll: false,
    });
  }
  return (
    <>
      <PageHeader
        title="Assessment Records"
        actions={
          <PageActionGroup>
            {access.canManage ? (
              <PageActionLink
                href="/portal/assessment-records/new"
                icon={FilePlus2}
                label="Record result"
                labelDetail="assessment"
              />
            ) : null}
            {access.canManageTypes ? (
              <PageActionLink
                href="/portal/assessment-records/types"
                icon={Settings2}
                label="Manage types"
                labelDetail="assessment"
                variant="secondary"
              />
            ) : null}
          </PageActionGroup>
        }
      />
      {list.isError && data ? (
        <RefreshFailureNotice
          onRetry={() => void list.refetch()}
          retrying={list.isFetching}
        />
      ) : null}
      <Panel aria-labelledby="assessment-results">
        <PanelHeader
          title="Results"
          titleId="assessment-results"
          context={
            data
              ? describeResultPage({
                  count: data.items.length,
                  page: data.page,
                  hasNext: data.has_next,
                  noun: { one: "record", other: "records" },
                  filtered,
                })
              : null
          }
        />
        {!data && list.isPending ? (
          <AssessmentLoading framed={false} />
        ) : !data && list.isError ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={
              <Button
                type="button"
                variant="secondary"
                disabled={list.isFetching}
                onClick={() => void list.refetch()}
              >
                Retry
              </Button>
            }
          >
            {assessmentErrorMessage(list.error)}
          </PanelMessage>
        ) : data?.items.length ? (
          <div className="max-w-full overflow-x-auto">
            <table className={dataTable.table}>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={dataTable.headerCell}>
                    Student
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Assessment
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Administered
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id} className={dataTable.row}>
                    <td className={dataTable.cell}>
                      <Link
                        href={`/portal/assessment-records/${item.id}`}
                        className="inline-flex min-h-11 items-center font-semibold text-brand underline-offset-4 hover:underline"
                      >
                        {item.student.display_name}
                      </Link>
                      <p className="text-xs text-muted">
                        {item.student.institutional_id ??
                          "Institutional ID not available"}
                      </p>
                    </td>
                    <td className={dataTable.cell}>
                      {item.assessment_type.name}
                      {!item.assessment_type.is_active ? (
                        <p className="text-xs text-muted">Inactive type</p>
                      ) : null}
                    </td>
                    <td className={dataTable.cell}>
                      {formatDateOnly(item.administered_on)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : data ? (
          <PanelMessage>
            {filtered
              ? "No Assessment Records match these filters."
              : "No assessment results have been recorded."}
          </PanelMessage>
        ) : null}
      </Panel>
      {data ? (
        <CanonicalPagination
          page={data.page}
          hasNext={data.has_next}
          label="Assessment Records pages"
          onPageChange={(nextPage) => {
            const next = new URLSearchParams(applied);
            next.set("page", String(nextPage));
            router.push("/portal/assessment-records?" + next, {
              scroll: false,
            });
          }}
        />
      ) : null}
      <form
        role="search"
        aria-label="Assessment Records filters"
        onSubmit={submit}
      >
        <FloatingListTools
          submits
          invalid={rangeInvalid}
          filterCount={filterCount}
          clear={
            filtered || order !== "NEWEST_ADMINISTERED" ? (
              <Link
                href="/portal/assessment-records"
                className={buttonVariants({ variant: "quiet" })}
              >
                Clear filters
              </Link>
            ) : undefined
          }
          filters={
            <>
              <FilterField
                label="Assessment Type"
                htmlFor="assessment-type-filter"
              >
                <Select
                  id="assessment-type-filter"
                  value={draft.type}
                  onChange={(event) => field("type", event.target.value)}
                >
                  <option value="">All types</option>
                  {typeData?.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                      {!type.is_active ? " (inactive)" : ""}
                    </option>
                  ))}
                </Select>
              </FilterField>
              {types.isError ? (
                <p role="alert" className="text-sm text-danger">
                  Assessment Types could not be loaded.{" "}
                  <Button
                    type="button"
                    variant="quiet"
                    onClick={() => void types.refetch()}
                  >
                    Retry types
                  </Button>
                </p>
              ) : null}
              <FilterField label="Administered from" htmlFor="assessment-from">
                <Input
                  id="assessment-from"
                  type="date"
                  value={draft.from}
                  onChange={(event) => field("from", event.target.value)}
                  aria-invalid={rangeInvalid}
                  aria-describedby={
                    rangeInvalid ? "assessment-range-error" : undefined
                  }
                />
              </FilterField>
              <FilterField label="Administered to" htmlFor="assessment-to">
                <Input
                  id="assessment-to"
                  type="date"
                  value={draft.to}
                  onChange={(event) => field("to", event.target.value)}
                  aria-invalid={rangeInvalid}
                  aria-describedby={
                    rangeInvalid ? "assessment-range-error" : undefined
                  }
                />
              </FilterField>
              <FilterField label="Order" htmlFor="assessment-order">
                <Select
                  id="assessment-order"
                  value={draft.ordering}
                  onChange={(event) => field("ordering", event.target.value)}
                >
                  {Object.entries(assessmentOrderLabels).map(
                    ([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ),
                  )}
                </Select>
              </FilterField>
              {rangeInvalid ? (
                <p
                  id="assessment-range-error"
                  role="alert"
                  className="text-sm text-danger"
                >
                  From date must not follow To date.
                </p>
              ) : null}
            </>
          }
        >
          <ListSearchField
            id="assessment-search"
            label="Search Students or Assessment Types"
            value={draft.search}
            onChange={(event) => field("search", event.target.value)}
            maxLength={160}
          />
        </FloatingListTools>
      </form>
    </>
  );
}
