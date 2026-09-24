"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { FormEvent } from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { FeedbackAccessUnavailable, FeedbackDate, FeedbackPageHeading, FeedbackQueryError, feedbackSelectClass } from "@/features/feedback/feedback-shared";
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
    <div className="grid gap-4 sm:grid-cols-2">
      <div><Label htmlFor="feedback-submitted-from">Submitted from</Label><Input id="feedback-submitted-from" className="mt-2" type="date" name="submitted_from" defaultValue={searchParams.get("submitted_from") ?? ""} /></div>
      <div><Label htmlFor="feedback-submitted-to">Submitted to</Label><Input id="feedback-submitted-to" className="mt-2" type="date" name="submitted_to" defaultValue={searchParams.get("submitted_to") ?? ""} /></div>
    </div>
  );
}

export function CustomerFeedbackResponseList() {
  const [filterError, setFilterError] = useState<string | null>(null);
  const { user } = usePortalSession();
  const access = getFeedbackAccess(user);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const params = new URLSearchParams(searchParams.toString());
  const search = (params.get("search") ?? "").trim();
  const serviceParam = params.get("service") ?? "";
  const service = Object.values(CustomerFeedbackServiceValue).includes(serviceParam as CustomerFeedbackServiceValue) ? serviceParam as CustomerFeedbackServiceValue : undefined;
  const page = getPage(params);
  const list = useFeedbackListCustomerFeedbackResponses({ ...(search ? { search } : {}), ...(service ? { service } : {}), ...(params.get("submitted_from") ? { submitted_from: params.get("submitted_from")! } : {}), ...(params.get("submitted_to") ? { submitted_to: params.get("submitted_to")! } : {}), page, page_size: 25 }, { query: { retry: false, enabled: access.canViewCustomerFeedback } });

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
    for (const key of ["search", "service", "submitted_from", "submitted_to"]) {
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

  const hasFilters = Boolean(search || service || params.get("submitted_from") || params.get("submitted_to"));
  const rows = list.data?.data;

  return (
    <section aria-labelledby="customer-feedback-responses-heading">
      <FeedbackPageHeading headingId="customer-feedback-responses-heading" title="Customer Feedback responses" description="Read-only access to submitted responses. Search is limited to respondent name." />
      <form key={searchParams.toString()} className="mt-5 border-y border-border py-5" onSubmit={applyFilters}>
        <div className="grid gap-4 lg:grid-cols-[minmax(16rem,1.3fr)_minmax(14rem,1fr)_minmax(20rem,1.2fr)] lg:items-end">
          <div><Label htmlFor="feedback-search">Search respondent name</Label><Input id="feedback-search" className="mt-2" name="search" type="search" placeholder="Search respondent name" defaultValue={search} /></div>
          <div><Label htmlFor="feedback-service-filter">Service</Label><select id="feedback-service-filter" className={`${feedbackSelectClass} mt-2`} name="service" defaultValue={service ?? ""}><option value="">All services</option>{feedbackServices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
          <DateRangeFilters searchParams={params} />
        </div>
        {filterError ? <p role="alert" className="mt-3 text-sm text-danger">{filterError}</p> : null}
        <div className="mt-4 flex flex-wrap gap-3"><Button type="submit" variant="secondary">Apply filters</Button>{hasFilters ? <Button variant="quiet" onClick={clearFilters}>Clear filters</Button> : null}</div>
      </form>
      {list.isPending ? <p aria-busy="true" className="py-8 text-sm text-muted">Loading Customer Feedback responses…</p> : list.isError ? <div className="mt-5"><FeedbackQueryError error={list.error} fallback="Customer Feedback responses could not be loaded." onRetry={() => void list.refetch()} /></div> : rows?.items.length === 0 ? <p className="border-b border-border py-9 text-sm text-muted">{hasFilters ? "No Customer Feedback responses match the current search or filters." : "No Customer Feedback responses have been submitted."}</p> : rows ? (
        <>
          {list.isFetching ? <p role="status" className="mt-3 text-xs text-muted">Refreshing responses…</p> : null}
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <caption className="sr-only">Customer Feedback response list</caption>
              <thead className="border-b border-border bg-surface-muted text-xs uppercase tracking-wide text-muted"><tr><th scope="col" className="sticky left-0 bg-surface-muted px-4 py-3">Respondent</th><th scope="col" className="px-4 py-3">Services received</th><th scope="col" className="px-4 py-3">Submitted</th></tr></thead>
              <tbody className="divide-y divide-border">{rows.items.map((item) => <tr key={item.id} className="align-top"><th scope="row" className="sticky left-0 bg-body px-4 py-4 font-semibold text-ink"><Link href={`/portal/feedback/customer-feedback/responses/${item.id}`} className="text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{item.respondent_name || "Name not provided"}</Link></th><td className="max-w-md px-4 py-4 text-muted">{item.services_received.map((value) => feedbackServices.find(([candidate]) => candidate === value)?.[1] ?? value).join(", ")}</td><td className="whitespace-nowrap px-4 py-4 text-muted"><FeedbackDate value={item.submitted_at} /></td></tr>)}</tbody>
            </table>
          </div>
          {rows.page > 1 || rows.has_next ? <nav aria-label="Customer Feedback response pagination" className="mt-5 flex items-center justify-between gap-4"><Button variant="secondary" disabled={rows.page <= 1} onClick={() => movePage(router, pathname, params, rows.page - 1)}>Previous</Button><span className="text-sm text-muted">Page {rows.page}</span><Button variant="secondary" disabled={!rows.has_next} onClick={() => movePage(router, pathname, params, rows.page + 1)}>Next</Button></nav> : null}
        </>
      ) : null}
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
  const rows = list.data?.data;

  return (
    <section aria-labelledby="csm-responses-heading">
      <FeedbackPageHeading headingId="csm-responses-heading" title="Client Satisfaction Measurement responses" description="Read-only access to submitted CSM responses. Service is a text filter against the service named in the response." />
      <form key={searchParams.toString()} className="mt-5 border-y border-border py-5" onSubmit={applyFilters}>
        <div className="grid gap-4 lg:grid-cols-[minmax(13rem,0.8fr)_minmax(15rem,1fr)_minmax(20rem,1.2fr)] lg:items-end">
          <div><Label htmlFor="csm-client-filter">Client type</Label><select id="csm-client-filter" className={`${feedbackSelectClass} mt-2`} name="client_type" defaultValue={clientType ?? ""}><option value="">All client types</option>{clientTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
          <div><Label htmlFor="csm-service-filter">Filter service availed</Label><Input id="csm-service-filter" className="mt-2" name="service" placeholder="Filter service availed" defaultValue={service} /></div>
          <DateRangeFilters searchParams={params} />
        </div>
        {filterError ? <p role="alert" className="mt-3 text-sm text-danger">{filterError}</p> : null}
        <div className="mt-4 flex flex-wrap gap-3"><Button type="submit" variant="secondary">Apply filters</Button>{hasFilters ? <Button variant="quiet" onClick={clearFilters}>Clear filters</Button> : null}</div>
      </form>
      {list.isPending ? <p aria-busy="true" className="py-8 text-sm text-muted">Loading CSM responses…</p> : list.isError ? <div className="mt-5"><FeedbackQueryError error={list.error} fallback="CSM responses could not be loaded." onRetry={() => void list.refetch()} /></div> : rows?.items.length === 0 ? <p className="border-b border-border py-9 text-sm text-muted">{hasFilters ? "No CSM responses match the current filters." : "No CSM responses have been submitted."}</p> : rows ? (
        <>
          {list.isFetching ? <p role="status" className="mt-3 text-xs text-muted">Refreshing responses…</p> : null}
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <caption className="sr-only">Client Satisfaction Measurement response list</caption>
              <thead className="border-b border-border bg-surface-muted text-xs uppercase tracking-wide text-muted"><tr><th scope="col" className="sticky left-0 bg-surface-muted px-4 py-3">Client type</th><th scope="col" className="px-4 py-3">Service availed</th><th scope="col" className="px-4 py-3">Submitted</th></tr></thead>
              <tbody className="divide-y divide-border">{rows.items.map((item) => <tr key={item.id} className="align-top"><th scope="row" className="sticky left-0 bg-body px-4 py-4 font-semibold text-ink"><Link href={`/portal/feedback/csm/responses/${item.id}`} className="text-brand underline hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{clientTypes.find(([candidate]) => candidate === item.client_type)?.[1] ?? item.client_type}</Link><span className="mt-1 block text-xs font-normal text-muted">Schema v{item.instrument_schema_version}</span></th><td className="max-w-md px-4 py-4 text-muted">{item.service_availed || "Not provided"}</td><td className="whitespace-nowrap px-4 py-4 text-muted"><FeedbackDate value={item.submitted_at} /></td></tr>)}</tbody>
            </table>
          </div>
          {rows.page > 1 || rows.has_next ? <nav aria-label="CSM response pagination" className="mt-5 flex items-center justify-between gap-4"><Button variant="secondary" disabled={rows.page <= 1} onClick={() => movePage(router, pathname, params, rows.page - 1)}>Previous</Button><span className="text-sm text-muted">Page {rows.page}</span><Button variant="secondary" disabled={!rows.has_next} onClick={() => movePage(router, pathname, params, rows.page + 1)}>Next</Button></nav> : null}
        </>
      ) : null}
    </section>
  );
}
