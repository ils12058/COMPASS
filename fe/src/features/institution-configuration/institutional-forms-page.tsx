"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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
      <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
        Institutional Forms
      </h1>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
        Read-only reference of controlled-form identities recognized by COMPASS. This is not
        an inventory of every questionnaire, workflow, report, or downloadable PDF.
      </p>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Official code and revision identify an institutional controlled document. Current means the revision selected for new records. COMPASS support means this deployed software understands that exact revision; it does not grant institutional approval. Supported revisions are synchronized with the deployed version after confirmed form changes.</p>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Some confirmed source revisions retain former CNSC/GTA codes. Current UCN branding does not rewrite their controlled-document identities.</p>
      {invalidFamilyNotice ? <p role="status" className="mt-4 border-y border-warning/30 py-3 text-sm text-warning">The requested Form Family is unavailable. Choose an available family below.</p> : null}

      {families.isError && !families.data ? (
        <div role="alert" className="mt-8 border-y border-danger/30 py-4">
          <p className="text-sm leading-6 text-danger">
            {institutionConfigurationErrorMessage(
              families.error,
              "Institutional Form Families could not be loaded.",
            )}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => void families.refetch()}>
            Retry
          </Button>
        </div>
      ) : families.isPending && !families.data ? (
        <div
          className="mt-8 grid gap-8 lg:grid-cols-[16rem_minmax(0,1fr)]"
          aria-busy="true"
        >
          <div className="space-y-3">
            <Skeleton className="h-6 w-36" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <p className="sr-only">Loading Institutional Form Families…</p>
          </div>
          <div className="space-y-3">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        </div>
      ) : familyItems.length === 0 ? (
        <p className="mt-8 border-y border-border py-5 text-sm text-muted">
          Institutional Form references are unavailable for this deployment. Supported Form Families have not been synchronized.
        </p>
      ) : (
        <div className="mt-8 grid min-w-0 gap-8 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <nav aria-label="Form families" className="min-w-0">
            <h2 className="font-heading text-lg font-semibold text-ink">
              Form families
            </h2>
            <ul className="mt-3 divide-y divide-border border-y border-border">
              {familyItems.map((family) => {
                const selected = family.id === selectedFamily?.id;
                return (
                  <li key={family.id}>
                    <Link
                      href={`/portal/institutional-forms?family=${encodeURIComponent(family.key)}`}
                      aria-current={selected ? "page" : undefined}
                      className={
                        "block min-h-12 break-words px-3 py-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
                        (selected
                          ? "border-l-4 border-brand bg-surface-muted text-ink"
                          : "text-muted hover:bg-surface-muted hover:text-ink")
                      }
                    >
                      {family.title}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {selectedFamily ? <section aria-labelledby="selected-form-family-heading" className="min-w-0">
            <div className="min-w-0 border-b border-border pb-5">
              <h2
                id="selected-form-family-heading"
                className="break-words font-heading text-2xl font-semibold text-ink"
              >
                {selectedFamily.title}
              </h2>
              <p className="mt-2 text-sm font-semibold text-ink">
                {selectedFamily.configuration_state === FormFamilyConfigurationState.READY ? "Current supported revision ready" :
                  selectedFamily.configuration_state === FormFamilyConfigurationState.REVISION_NOT_REQUIRED ? "Controlled revision not required" :
                  selectedFamily.configuration_state === FormFamilyConfigurationState.ACTIVE_UNSUPPORTED ? "Configuration mismatch" :
                  "Required revision missing"}
              </p>
              {selectedFamily.configuration_state === FormFamilyConfigurationState.ACTIVE_UNSUPPORTED ? <p role="alert" className="mt-2 max-w-2xl text-sm leading-6 text-danger">A revision is marked Current for new records, but this COMPASS version does not support its exact controlled-form identity.</p> : null}
              {selectedFamily.configuration_state === FormFamilyConfigurationState.MISSING_REQUIRED_REVISION ? <p role="alert" className="mt-2 max-w-2xl text-sm leading-6 text-danger">This Form Family requires a current supported revision, but none is configured.</p> : null}
            </div>

            <h3 className="mt-6 font-heading text-lg font-semibold text-ink">
              Form Revisions
            </h3>
            {revisions.isError && !revisions.data ? (
              <div role="alert" className="mt-4 border-y border-danger/30 py-4">
                <p className="text-sm leading-6 text-danger">
                  {institutionConfigurationErrorMessage(
                    revisions.error,
                    "Form Revisions for this family could not be loaded.",
                  )}
                </p>
                <Button
                  variant="secondary"
                  className="mt-3"
                  onClick={() => void revisions.refetch()}
                >
                  Retry
                </Button>
              </div>
            ) : revisions.isPending && !revisions.data ? (
              <div className="mt-4 space-y-3" aria-busy="true">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <p className="sr-only">Loading Form Revisions…</p>
              </div>
            ) : revisionItems.length === 0 ? (
              <div className="mt-4 border-y border-border py-5">
                <p className="text-sm leading-6 text-muted">
                  {selectedFamily.configuration_state === FormFamilyConfigurationState.REVISION_NOT_REQUIRED
                    ? "No confirmed controlled-document revision is required for this Form Family. COMPASS supports its current schema without inventing an official code or revision."
                    : "No Form Revision is recorded for this family."}
                </p>
              </div>
            ) : (
              <>
                {revisions.isError ? (
                  <p role="alert" className="mt-4 text-sm leading-6 text-danger">
                    The revision list could not be refreshed. The displayed data may be out
                    of date.
                  </p>
                ) : null}
                <div className="mt-4">
                  <FormRevisionList
                    familyTitle={selectedFamily.title}
                    revisions={revisionItems}
                  />
                </div>
              </>
            )}
          </section> : <p className="text-sm text-muted">Choose a Form Family to view its revisions.</p>}
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
