"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { InstitutionalFormsHelp } from "@/features/institution-configuration/forms-help";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { canViewInstitutionalForms } from "@/features/institution-configuration/institution-access";
import { institutionConfigurationErrorMessage } from "@/features/institution-configuration/institution-action";
import { FormRevisionList } from "@/features/institution-configuration/form-revision-list";
import { InstitutionWorkspaceUnavailable } from "@/features/institution-configuration/institution-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useInstitutionalFormsList,
  useInstitutionalFormsRevisionsList,
} from "@/lib/api/generated/institutional-forms/institutional-forms";
import { FormFamilyConfigurationState } from "@/lib/api/generated/model";

export function InstitutionalFormsPage({
  requestedFamily,
}: {
  requestedFamily?: string;
}) {
  const { user } = usePortalSession();

  if (!canViewInstitutionalForms(user)) {
    return <InstitutionWorkspaceUnavailable workspace="Institutional Forms" />;
  }

  return <InstitutionalFormsWorkspace requestedFamily={requestedFamily} />;
}

function InstitutionalFormsWorkspace({
  requestedFamily,
}: {
  requestedFamily?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const families = useInstitutionalFormsList();
  const familyItems = families.data?.data.items ?? [];
  const selectedFamily = requestedFamily
    ? familyItems.find((family) => family.key === requestedFamily)
    : familyItems[0];
  const invalidFamilyNotice = Boolean(
    families.isSuccess &&
      ((requestedFamily && !selectedFamily) || searchParams.get("family_unavailable") === "1"),
  );
  const revisions = useInstitutionalFormsRevisionsList(
    selectedFamily?.key ?? "",
    { query: { enabled: Boolean(selectedFamily) } },
  );
  const revisionItems = revisions.data?.data.items ?? [];

  useEffect(() => {
    if (!families.isSuccess) return;
    if (requestedFamily && !selectedFamily) {
      router.replace(`${pathname}?family_unavailable=1`, { scroll: false });
      return;
    }
    if (requestedFamily && selectedFamily) return;
    if (selectedFamily) {
      if (invalidFamilyNotice) return;
      router.replace(
        `${pathname}?family=${encodeURIComponent(selectedFamily.key)}`,
        { scroll: false },
      );
      return;
    }
  }, [families.isSuccess, invalidFamilyNotice, pathname, requestedFamily, router, selectedFamily]);

  return (
    <>
      <PageHeader
        title="Institutional Forms"
        description="Controlled forms recognized by COMPASS."
        help={<InstitutionalFormsHelp />}
      >
      </PageHeader>
      {invalidFamilyNotice ? <Notice role="status" tone="warning" className="mb-5">The requested Form Family is unavailable. Choose an available family below.</Notice> : null}

      {families.isError && !families.data ? (
        <Notice
          role="alert"
          tone="danger"
          action={
            <Button variant="secondary" onClick={() => void families.refetch()}>
              Retry
            </Button>
          }
        >
          {institutionConfigurationErrorMessage(
            families.error,
            "Institutional Form Families could not be loaded.",
          )}
        </Notice>
      ) : families.isPending && !families.data ? (
        <div className="grid gap-5 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <RowsSkeleton label="Loading institutional form families…" rows={3} framed />
          <div className="rounded-sm border border-brand-line bg-surface-raised px-4 py-4 sm:px-5" aria-hidden="true">
            <Skeleton className="h-6 w-64" />
            <Skeleton className="mt-4 h-16 w-full" />
            <Skeleton className="mt-3 h-16 w-full" />
          </div>
        </div>
      ) : familyItems.length === 0 ? (
        <Panel><PanelMessage>No Institutional Form references are available.</PanelMessage></Panel>
      ) : (
        <div className="grid min-w-0 items-start gap-5 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <nav aria-labelledby="form-families-heading" className="min-w-0 rounded-sm border border-brand-line bg-surface-raised">
            <h2 id="form-families-heading" className="border-b border-brand-line px-4 py-3 font-heading text-base font-semibold text-ink">
              Form families
            </h2>
            <ul className="divide-y divide-border">
              {familyItems.map((family) => {
                const selected = family.id === selectedFamily?.id;
                return (
                  <li key={family.id}>
                    <Link
                      href={`/portal/institutional-forms?family=${encodeURIComponent(family.key)}`}
                      aria-current={selected ? "page" : undefined}
                      className={
                        "block min-h-12 break-words px-4 py-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus " +
                        (selected
                          ? "bg-brand-wash text-brand-strong"
                          : "text-muted hover:bg-surface-subtle hover:text-ink")
                      }
                    >
                      {family.title}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {selectedFamily ? <Panel aria-labelledby="selected-form-family-heading">
            <PanelHeader
              title={selectedFamily.title}
              titleId="selected-form-family-heading"
              description={
                <span className="font-semibold text-ink">
                  {selectedFamily.configuration_state === FormFamilyConfigurationState.READY ? "Current supported revision ready" :
                    selectedFamily.configuration_state === FormFamilyConfigurationState.REVISION_NOT_REQUIRED ? "Controlled revision not required" :
                    selectedFamily.configuration_state === FormFamilyConfigurationState.ACTIVE_UNSUPPORTED ? "Configuration mismatch" :
                    "Required revision missing"}
                </span>
              }
            />
            {selectedFamily.configuration_state === FormFamilyConfigurationState.ACTIVE_UNSUPPORTED ? <p role="alert" className="border-b border-brand-line px-4 py-3 text-sm leading-6 text-danger sm:px-5">The Current revision is not supported by this version of COMPASS.</p> : null}
            {selectedFamily.configuration_state === FormFamilyConfigurationState.MISSING_REQUIRED_REVISION ? <p role="alert" className="border-b border-brand-line px-4 py-3 text-sm leading-6 text-danger sm:px-5">A current supported revision is required for this form family.</p> : null}

            <h3 className="px-4 pb-3 pt-4 font-heading text-base font-semibold text-ink sm:px-5">
              Form Revisions
            </h3>
            {revisions.isError && !revisions.data ? (
              <PanelMessage
                role="alert"
                tone="danger"
                className="pt-0"
                action={
                  <Button variant="secondary" onClick={() => void revisions.refetch()}>
                    Retry
                  </Button>
                }
              >
                {institutionConfigurationErrorMessage(
                  revisions.error,
                  "Form Revisions for this family could not be loaded.",
                )}
              </PanelMessage>
            ) : revisions.isPending && !revisions.data ? (
              <RowsSkeleton label="Loading form revisions…" rows={2} className="border-t border-border" />
            ) : revisionItems.length === 0 ? (
              <PanelMessage className="pt-0">
                {selectedFamily.configuration_state === FormFamilyConfigurationState.REVISION_NOT_REQUIRED
                  ? "No official controlled-document revision is required for this form family in COMPASS."
                  : "No Form Revision is recorded for this family."}
              </PanelMessage>
            ) : (
              <>
                {revisions.isError ? (
                  <p role="alert" className="px-4 pb-3 text-sm leading-6 text-danger sm:px-5">
                    The revision list could not be refreshed. The displayed data may be out
                    of date.
                  </p>
                ) : null}
                <FormRevisionList
                  familyTitle={selectedFamily.title}
                  revisions={revisionItems}
                />
              </>
            )}
          </Panel> : <Panel><PanelMessage>Choose a Form Family to view its revisions.</PanelMessage></Panel>}
        </div>
      )}

      {families.isError && families.data ? (
        <p role="alert" className="mt-4 text-sm leading-6 text-danger">
          The Form Family list could not be refreshed. The displayed data may be out of date.
        </p>
      ) : null}
    </>
  );
}
