"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { canManageInstitutionalForms, canViewInstitutionalForms } from "@/features/institution-configuration/institution-access";
import { institutionConfigurationErrorMessage } from "@/features/institution-configuration/institution-action";
import { InstitutionWorkspaceUnavailable } from "@/features/institution-configuration/institution-shared";
import { FormRevisionList } from "@/features/institution-configuration/form-revision-list";
import { FormRevisionRegistration } from "@/features/institution-configuration/form-revision-registration";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useInstitutionalFormsList,
  useInstitutionalFormsRevisionsList,
} from "@/lib/api/generated/institutional-forms/institutional-forms";

export function InstitutionalFormsPage({
  requestedFamily,
}: {
  requestedFamily?: string;
}) {
  const { user } = usePortalSession();

  if (!canViewInstitutionalForms(user)) {
    return <InstitutionWorkspaceUnavailable workspace="Institutional Forms" />;
  }

  return (
    <InstitutionalFormsWorkspace
      requestedFamily={requestedFamily}
      canManage={canManageInstitutionalForms(user)}
    />
  );
}

function InstitutionalFormsWorkspace({
  requestedFamily,
  canManage,
}: {
  requestedFamily?: string;
  canManage: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const families = useInstitutionalFormsList();
  const familyItems = families.data?.data.items ?? [];
  const selectedFamily =
    familyItems.find((family) => family.key === requestedFamily) ??
    familyItems[0];
  const revisions = useInstitutionalFormsRevisionsList(
    selectedFamily?.key ?? "",
    { query: { enabled: Boolean(selectedFamily) } },
  );
  const revisionItems = revisions.data?.data.items ?? [];

  useEffect(() => {
    if (!families.isSuccess) return;
    if (selectedFamily) {
      if (requestedFamily === selectedFamily.key) return;
      router.replace(
        `${pathname}?family=${encodeURIComponent(selectedFamily.key)}`,
        { scroll: false },
      );
      return;
    }
    if (requestedFamily) router.replace(pathname, { scroll: false });
  }, [families.isSuccess, pathname, requestedFamily, router, selectedFamily]);

  return (
    <>
      <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
        Institutional Forms
      </h1>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
        Manage QMS-issued Form Family and revision metadata. This workspace does not edit or preview the forms themselves.
      </p>

      {families.isError && !families.data ? (
        <p role="alert" className="mt-8 border-y border-danger/30 py-4 text-sm leading-6 text-danger">
          {institutionConfigurationErrorMessage(
            families.error,
            "Institutional Form Families could not be loaded. Try again.",
          )}
        </p>
      ) : families.isPending && !families.data ? (
        <div className="mt-8 grid gap-8 lg:grid-cols-[16rem_minmax(0,1fr)]" aria-busy="true">
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
          No Institutional Form Families are available.
        </p>
      ) : selectedFamily ? (
        <div className="mt-8 grid min-w-0 gap-8 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <nav aria-label="Form families" className="min-w-0">
            <h2 className="font-heading text-lg font-semibold text-ink">
              Form families
            </h2>
            <ul className="mt-3 divide-y divide-border border-y border-border">
              {familyItems.map((family) => {
                const selected = family.id === selectedFamily.id;
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

          <section aria-labelledby="selected-form-family-heading" className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
              <div className="min-w-0">
                <h2
                  id="selected-form-family-heading"
                  className="break-words font-heading text-2xl font-semibold text-ink"
                >
                  {selectedFamily.title}
                </h2>
                <p className="mt-2 break-all text-sm text-muted">
                  Family key: <code className="font-mono">{selectedFamily.key}</code>
                </p>
              </div>
              {canManage ? (
                <FormRevisionRegistration
                  familyKey={selectedFamily.key}
                  familyTitle={selectedFamily.title}
                />
              ) : null}
            </div>

            <h3 className="mt-6 font-heading text-lg font-semibold text-ink">
              Form Revisions
            </h3>
            {revisions.isError && !revisions.data ? (
              <p role="alert" className="mt-4 border-y border-danger/30 py-4 text-sm leading-6 text-danger">
                {institutionConfigurationErrorMessage(
                  revisions.error,
                  "Form Revisions for this family could not be loaded. Try again.",
                )}
              </p>
            ) : revisions.isPending && !revisions.data ? (
              <div className="mt-4 space-y-3" aria-busy="true">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <p className="sr-only">Loading Form Revisions…</p>
              </div>
            ) : revisionItems.length === 0 ? (
              <div className="mt-4 border-y border-border py-5">
                <p className="text-sm text-ink">
                  No Form Revisions are registered for this Form Family.
                </p>
                {canManage ? (
                  <p className="mt-2 text-sm leading-6 text-muted">
                    Register a Form Revision to record its official QMS identity.
                  </p>
                ) : null}
              </div>
            ) : (
              <>
                {revisions.isError ? (
                  <p role="alert" className="mt-4 text-sm leading-6 text-danger">
                    The revision list could not be refreshed. The displayed data may be out of date.
                  </p>
                ) : null}
                <div className="mt-4">
                  <FormRevisionList
                    familyKey={selectedFamily.key}
                    familyTitle={selectedFamily.title}
                    revisions={revisionItems}
                    canManage={canManage}
                  />
                </div>
              </>
            )}
          </section>
        </div>
      ) : null}

      {families.isError && families.data ? (
        <p role="alert" className="mt-4 text-sm leading-6 text-danger">
          The Form Family list could not be refreshed. The displayed data may be out of date.
        </p>
      ) : null}
    </>
  );
}
