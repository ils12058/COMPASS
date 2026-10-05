"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { FormEvent } from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { dataTable } from "@/components/ui/data-table";
import { FormRevisionFilter } from "@/features/institutional-forms/form-revision-filter";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { FeedbackListSkeleton, FeedbackAccessUnavailable, FeedbackDate, FeedbackPageHeading, feedbackErrorMessage } from "@/features/feedback/feedback-shared";
import { describeResultPage } from "@/features/portal/components/result-context";
import { useFeedbackListCustomerFeedbackResponses, useFeedbackListCsmResponses } from "@/lib/api/generated/feedback/feedback";
import { CSMClientTypeValue, CustomerFeedbackServiceValue } from "@/lib/api/generated/model";

const feedbackServices = [
  [CustomerFeedbackServiceValue.COUNSELING, "Counseling"],
  [CustomerFeedbackServiceValue.ADMISSION, "Admission"],
  [CustomerFeedbackServiceValue.TESTING, "Testing"],
  [CustomerFeedbackServiceValue.EDUCATIONAL_INFORMATION, "Educational Information"],
  [CustomerFeedbackServiceValue.REQUEST_FOR_CERTIFICATION, "Request for Certification"],
  [CustomerFeedbackServiceValue.APPLICATION_FOR_ADMISSION_TEST, "Application for Admission Test"],
  [CustomerFeedbackServiceValue.OTHER, "Others"],
] as const;

const clientTypes = [
  [CSMClientTypeValue.CITIZEN, "Citizen"],
  [CSMClientTypeValue.BUSINESS, "Business"],
  [CSMClientTypeValue.GOVERNMENT, "Government"],
] as const;

function queryString(params: URLSearchParams): string {
  const query = params.toString();
  return query ? `?${query}` : "";
}

function getPage(searchParams: URLSearchParams): number {
  const requested = Number.parseInt(searchParams.get("page") ?? "1", 10);
  return Number.isFinite(requested) && requested > 0 ? requested : 1;
}

function movePage(router: ReturnType<typeof useRouter>, pathname: string, searchParams: URLSearchParams, page: number) {
  const next = new URLSearchParams(searchParams.toString());
  next.set("page", String(page));
  router.push(`${pathname}${queryString(next)}`);
}

function DateRangeFilters({ searchParams }: { searchParams: URLSearchParams }) {
  return (
    <>
      <FilterField label="Submitted from" htmlFor="feedback-submitted-from"><Input id="feedback-submitted-from" type="date" name="submitted_from" defaultValue={searchParams.get("submitted_from") ?? ""} /></FilterField>
      <FilterField label="Submitted to" htmlFor="feedback-submitted-to"><Input id="feedback-submitted-to" type="date" name="submitted_to" defaultValue={searchParams.get("submitted_to") ?? ""} /></FilterField>
    </>
  );
}

const responseTable = `${dataTable.table} min-w-[46rem]`;

export function CustomerFeedbackResponseList() {
  const [filterError, setFilterError] = useState<string | null>(null);
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const params = new URLSearchParams(searchParams.toString());
  const search = (params.get("search") ?? "").trim();
  const formRevisionId = params.get("form_revision_id") ?? "";
  const serviceParam = params.get("service") ?? "";
  const service = Object.values(CustomerFeedbackServiceValue).includes(serviceParam as CustomerFeedbackServiceValue) ? serviceParam as CustomerFeedbackServiceValue : undefined;
  const page = getPage(params);
  const list = useFeedbackListCustomerFeedbackResponses({ ...(formRevisionId ? { form_revision_id: formRevisionId } : {}), ...(search ? { search } : {}), ...(service ? { service } : {}), ...(params.get("submitted_from") ? { submitted_from: params.get("submitted_from")! } : {}), ...(params.get("submitted_to") ? { submitted_to: params.get("submitted_to")! } : {}), page, page_size: 25 }, { query: { retry: false, enabled: access.canViewCustomerFeedback } });

  if (!access.canViewCustomerFeedback) return <FeedbackAccessUnavailable title="Customer Feedback responses unavailable" />;

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const submittedFrom = String(data.get("submitted_from") ?? "");
    const submittedTo = String(data.get("submitted_to") ?? "");
    if (submittedFrom && submittedTo && submittedFrom > submittedTo) {
      setFilterError("Submitted-to date must be on or after submitted-from date.");
      return;
    }
    setFilterError(null);
    const next = new URLSearchParams();
    for (const key of ["search", "service", "submitted_from", "submitted_to", "form_revision_id"]) {
      const value = String(data.get(key) ?? "").trim();
      if (value) next.set(key, value);
    }
    next.set("page", "1");
    router.push(`${pathname}${queryString(next)}`);
  }

  function clearFilters() {
    setFilterError(null);
    router.push(pathname);
  }

  const hasFilters = Boolean(formRevisionId || search || service || params.get("submitted_from") || params.get("submitted_to"));
  const rows = safeQueryData(list)?.data;

  return (
    <section aria-labelledby="customer-feedback-responses-heading">
      <FeedbackPageHeading headingId="customer-feedback-responses-heading" title="Customer Feedback responses" description="Responses are read-only. Search matches the respondent name only." />
      <form key={searchParams.toString()} role="search" aria-label="Customer Feedback responses" onSubmit={applyFilters}>
        <FloatingListTools
          submits
          invalid={Boolean(filterError)}
          filterCount={[formRevisionId, service, params.get("submitted_from"), params.get("submitted_to")].filter(Boolean).length}
          clear={hasFilters ? <Button variant="quiet" onClick={clearFilters}>Clear filters</Button> : undefined}
          filters={<>
            <FilterField label="Service" htmlFor="feedback-service-filter" className="sm:col-span-2"><Select id="feedback-service-filter" name="service" defaultValue={service ?? ""}><option value="">All services</option>{feedbackServices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></FilterField>
            <FormRevisionFilter id="feedback-revision" selectedId={formRevisionId} defaultValue={formRevisionId} options={rows?.filter_options.form_revisions} />
            <DateRangeFilters searchParams={params} />
            {filterError ? <p role="alert" className="text-sm text-danger sm:col-span-full">{filterError}</p> : null}
          </>}
        >
          <ListSearchField id="feedback-search" name="search" label="Search respondent name" placeholder="Search respondent name" defaultValue={search} />
        </FloatingListTools>
      </form>
      {list.isError && rows ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}
      <Panel aria-labelledby="customer-feedback-results-heading">
        <PanelHeader
          title="Responses"
          titleId="customer-feedback-results-heading"
          context={list.isFetching && !list.isPending ? "Refreshing responses…" : rows ? describeResultPage({ count: rows.items.length, page: rows.page, hasNext: rows.has_next, noun: { one: "response", other: "responses" }, filtered: hasFilters }) : null}
        />
        {list.isPending ? <FeedbackListSkeleton label="Loading Customer Feedback responses…" /> : !rows ? <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void list.refetch()}>Retry</Button>}>{feedbackErrorMessage(list.error, "Customer Feedback responses could not be loaded.")}</PanelMessage> : rows.items.length === 0 ? <PanelMessage>{hasFilters ? "No Customer Feedback responses match the current search or filters." : "No Customer Feedback responses have been submitted."}</PanelMessage> : (
          <div className={dataTable.scroll}>
            <table className={responseTable}>
              <caption className="sr-only">Customer Feedback response list</caption>
              <thead className={dataTable.head}><tr><th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>Respondent</th><th scope="col" className={dataTable.headerCell}>Services received</th><th scope="col" className={dataTable.headerCell}>Submitted</th></tr></thead>
              <tbody className={dataTable.body}>{rows.items.map((item) => <tr key={item.id} className={dataTable.row}><th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-semibold text-ink`}><Link href={`/portal/feedback/customer-feedback/responses/${item.id}`} className="text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{item.respondent_name || "Name not provided"}</Link></th><td className={`${dataTable.cell} max-w-md text-muted`}>{item.services_received.map((value) => feedbackServices.find(([candidate]) => candidate === value)?.[1] ?? value).join(", ")}</td><td className={`${dataTable.cell} whitespace-nowrap text-muted`}><FeedbackDate value={item.submitted_at} /></td></tr>)}</tbody>
            </table>
          </div>
        )}
        {rows ? <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" page={rows.page} hasNext={rows.has_next} label="Customer Feedback response pagination" onPageChange={(page) => movePage(router, pathname, params, page)} /> : null}
      </Panel>
    </section>
  );
}

export function CsmResponseList() {
  const [filterError, setFilterError] = useState<string | null>(null);
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const params = new URLSearchParams(searchParams.toString());
  const clientParam = params.get("client_type") ?? "";
  const clientType = Object.values(CSMClientTypeValue).includes(clientParam as CSMClientTypeValue) ? clientParam as CSMClientTypeValue : undefined;
  const service = (params.get("service") ?? "").trim();
  const page = getPage(params);
  const list = useFeedbackListCsmResponses({ ...(clientType ? { client_type: clientType } : {}), ...(service ? { service } : {}), ...(params.get("submitted_from") ? { submitted_from: params.get("submitted_from")! } : {}), ...(params.get("submitted_to") ? { submitted_to: params.get("submitted_to")! } : {}), page, page_size: 25 }, { query: { retry: false, enabled: access.canViewCsm } });

  if (!access.canViewCsm) return <FeedbackAccessUnavailable title="CSM responses unavailable" />;

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const submittedFrom = String(data.get("submitted_from") ?? "");
    const submittedTo = String(data.get("submitted_to") ?? "");
    if (submittedFrom && submittedTo && submittedFrom > submittedTo) {
      setFilterError("Submitted-to date must be on or after submitted-from date.");
      return;
    }
    setFilterError(null);
    const next = new URLSearchParams();
    for (const key of ["client_type", "service", "submitted_from", "submitted_to"]) {
      const value = String(data.get(key) ?? "").trim();
      if (value) next.set(key, value);
    }
    next.set("page", "1");
    router.push(`${pathname}${queryString(next)}`);
  }

  function clearFilters() { setFilterError(null); router.push(pathname); }
  const hasFilters = Boolean(clientType || service || params.get("submitted_from") || params.get("submitted_to"));
  const rows = safeQueryData(list)?.data;

  return (
    <section aria-labelledby="csm-responses-heading">
      <FeedbackPageHeading headingId="csm-responses-heading" title="Client Satisfaction Measurement responses" description="Responses are read-only. The service search matches the service named in each response." />
      <form key={searchParams.toString()} role="search" aria-label="CSM responses" onSubmit={applyFilters}>
        <FloatingListTools
          submits
          invalid={Boolean(filterError)}
          filterCount={[clientType, params.get("submitted_from"), params.get("submitted_to")].filter(Boolean).length}
          clear={hasFilters ? <Button variant="quiet" onClick={clearFilters}>Clear filters</Button> : undefined}
          filters={<>
            <FilterField label="Client type" htmlFor="csm-client-filter" className="sm:col-span-2"><Select id="csm-client-filter" name="client_type" defaultValue={clientType ?? ""}><option value="">All client types</option>{clientTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></FilterField>
            <DateRangeFilters searchParams={params} />
            {filterError ? <p role="alert" className="text-sm text-danger sm:col-span-full">{filterError}</p> : null}
          </>}
        >
          <ListSearchField id="csm-service-filter" name="service" label="Filter by service availed" placeholder="Filter by service availed" defaultValue={service} />
        </FloatingListTools>
      </form>
      {list.isError && rows ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}
      <Panel aria-labelledby="csm-results-heading">
        <PanelHeader
          title="Responses"
          titleId="csm-results-heading"
          context={list.isFetching && !list.isPending ? "Refreshing responses…" : rows ? describeResultPage({ count: rows.items.length, page: rows.page, hasNext: rows.has_next, noun: { one: "response", other: "responses" }, filtered: hasFilters }) : null}
        />
        {list.isPending ? <FeedbackListSkeleton label="Loading CSM responses…" /> : !rows ? <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void list.refetch()}>Retry</Button>}>{feedbackErrorMessage(list.error, "CSM responses could not be loaded.")}</PanelMessage> : rows.items.length === 0 ? <PanelMessage>{hasFilters ? "No CSM responses match the current filters." : "No CSM responses have been submitted."}</PanelMessage> : (
          <div className={dataTable.scroll}>
            <table className={responseTable}>
              <caption className="sr-only">Client Satisfaction Measurement response list</caption>
              <thead className={dataTable.head}><tr><th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>Client type</th><th scope="col" className={dataTable.headerCell}>Service availed</th><th scope="col" className={dataTable.headerCell}>Submitted</th></tr></thead>
              <tbody className={dataTable.body}>{rows.items.map((item) => <tr key={item.id} className={dataTable.row}><th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-semibold text-ink`}><Link href={`/portal/feedback/csm/responses/${item.id}`} className="text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{clientTypes.find(([candidate]) => candidate === item.client_type)?.[1] ?? item.client_type}</Link></th><td className={`${dataTable.cell} max-w-md text-muted`}>{item.service_availed || "Not provided"}</td><td className={`${dataTable.cell} whitespace-nowrap text-muted`}><FeedbackDate value={item.submitted_at} /></td></tr>)}</tbody>
            </table>
          </div>
        )}
        {rows ? <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" page={rows.page} hasNext={rows.has_next} label="CSM response pagination" onPageChange={(page) => movePage(router, pathname, params, page)} /> : null}
      </Panel>
    </section>
  );
}
