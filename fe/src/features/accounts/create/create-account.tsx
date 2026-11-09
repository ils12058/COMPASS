"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";

import { FacultyCollegeField } from "@/features/accounts/components/faculty-college-field";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter } from "@/components/ui/panel";
import {
  ManagedActionFeedback,
  useInvalidateManagedAccount,
  useManagedAction,
} from "@/features/accounts/components/account-action";
import {
  isRoleCode,
  roleLabels,
  roles,
} from "@/features/accounts/presentation";
import { useAccountsFacultyCollegeChoices, useAccountsCreate } from "@/lib/api/generated/accounts/accounts";
import { RoleCode, type AccountCreateRequest } from "@/lib/api/generated/model";

const fieldClass = "grid gap-2";

export function CreateAccount() {
  const router = useRouter();
  const session = usePortalSession();
  const create = useAccountsCreate();
  const action = useManagedAction();
  const invalidate = useInvalidateManagedAccount();
  const [form, setForm] = useState<AccountCreateRequest>({
    institutional_id: "",
    email: "",
    first_name: "",
    middle_name: "",
    last_name: "",
    suffix: "",
    role: RoleCode.STUDENT,
    is_active: true,
  });
  const [placementCampusId, setPlacementCampusId] = useState("");
  const [placementCollegeId, setPlacementCollegeId] = useState("");
  const [placementError, setPlacementError] = useState<string | null>(null);
  const [review, setReview] = useState<AccountCreateRequest | null>(null);
  const canAssignPlacement = session.user.capabilities.includes("student_academics.manage");
  const showPlacement = form.role === RoleCode.STUDENT && canAssignPlacement;
  const collegeChoices = useAccountsFacultyCollegeChoices({
    query: { enabled: form.role === RoleCode.FACULTY || showPlacement, retry: false },
  });
  const selectedFacultyCollege = collegeChoices.data?.data.find((college) => college.id === form.faculty_college_id);
  const campuses = useMemo(() => {
    const unique = new Map<string, { id: string; code: string; name: string }>();
    for (const college of collegeChoices.data?.data ?? []) {
      if (!unique.has(college.campus_id)) {
        unique.set(college.campus_id, {
          id: college.campus_id,
          code: college.campus_code,
          name: college.campus_name,
        });
      }
    }
    return [...unique.values()];
  }, [collegeChoices.data]);
  const placementColleges = (collegeChoices.data?.data ?? []).filter(
    (college) => college.campus_id === placementCampusId,
  );
  const reviewedCampus = review?.student_campus_id
    ? campuses.find((campus) => campus.id === review.student_campus_id)
    : undefined;
  const reviewedCollege = review?.student_college_id
    ? collegeChoices.data?.data.find((college) => college.id === review.student_college_id)
    : undefined;

  function change<K extends keyof AccountCreateRequest>(
    field: K,
    value: AccountCreateRequest[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    action.setError(null);
    action.setNotice(null);
    const campusId = showPlacement ? placementCampusId : "";
    const collegeId = showPlacement ? placementCollegeId : "";
    if ((campusId === "") !== (collegeId === "")) {
      setPlacementError("Select both Campus and College, or neither.");
      return;
    }
    setPlacementError(null);
    setReview({
      ...form,
      faculty_college_id: form.role === RoleCode.FACULTY ? form.faculty_college_id || null : null,
      student_campus_id: collegeId ? campusId : null,
      student_college_id: collegeId || null,
    });
  }

  async function confirmCreate() {
    if (!review) return;
    const reviewed = review;
    const response = await action.run(
      () => create.mutateAsync({ data: reviewed }),
      "Couldn't create the account. Try again.",
      () => setReview(null),
      undefined,
    );
    if (!response) return;
    setReview(null);
    await invalidate();
    router.push(`/portal/accounts/${encodeURIComponent(response.data.id)}`);
  }

  const reviewName = review
    ? [review.first_name, review.middle_name, review.last_name, review.suffix]
        .filter((part) => part?.trim())
        .join(" ")
    : "";

  return (
    <section aria-labelledby="create-account-heading" className="max-w-2xl">
      <PageHeader
        title="Create account"
        headingId="create-account-heading"
        back={
          <Link href="/portal/accounts" className={pageBackLinkClass}>
            Back to Accounts
          </Link>
        }
        description="The account holder can set up a COMPASS password using the registered email address."
      />
      <Panel as="div">
      <form onSubmit={(event) => void submit(event)}>
        <PanelBody className="space-y-6 py-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <div className={fieldClass}>
            <Label htmlFor="create-institutional-id">Institutional ID</Label>
            <Input
              id="create-institutional-id"
              required
              value={form.institutional_id}
              onChange={(event) =>
                change("institutional_id", event.target.value)
              }
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-email">Email</Label>
            <Input
              id="create-email"
              type="email"
              required
              value={form.email}
              onChange={(event) => change("email", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-first-name">First name</Label>
            <Input
              id="create-first-name"
              required
              value={form.first_name}
              onChange={(event) => change("first_name", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-middle-name">Middle name</Label>
            <Input
              id="create-middle-name"
              value={form.middle_name ?? ""}
              onChange={(event) => change("middle_name", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-last-name">Last name</Label>
            <Input
              id="create-last-name"
              required
              value={form.last_name}
              onChange={(event) => change("last_name", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-suffix">Suffix</Label>
            <Input
              id="create-suffix"
              value={form.suffix ?? ""}
              onChange={(event) => change("suffix", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-role">Role</Label>
            <Select
              id="create-role"
              value={form.role}
              onChange={(event) => {
                if (isRoleCode(event.target.value)) {
                  change("role", event.target.value);
                  setPlacementError(null);
                }
              }}
            >
              {roles.map((role) => (
                <option key={role} value={role}>
                  {roleLabels[role]}
                </option>
              ))}
            </Select>
          </div>
        </div>
        {form.role === RoleCode.FACULTY ? <FacultyCollegeField id="create-faculty-college" value={form.faculty_college_id ?? ""} onChange={(value) => change("faculty_college_id", value || null)} /> : null}
        {showPlacement ? (
          <fieldset className="grid gap-4 rounded-md border border-border p-4">
            <legend className="px-1 text-sm font-semibold text-ink">Initial academic placement (optional)</legend>
            <p className="text-sm text-muted">
              This placement is unverified and doesn&apos;t confirm enrollment. Make later changes in Student academic records.
            </p>
            {collegeChoices.isPending ? <p role="status" className="text-sm text-muted">Loading Campus and College choices…</p> : null}
            {collegeChoices.isError ? (
              <p role="alert" className="text-sm text-danger">
                Couldn&apos;t load campus and College choices. Try again.{" "}
                <Button variant="quiet" onClick={() => void collegeChoices.refetch()}>Retry</Button>
              </p>
            ) : null}
            <div className="grid gap-5 sm:grid-cols-2">
              <div className={fieldClass}>
                <Label htmlFor="create-student-campus">Campus</Label>
                <Select
                  id="create-student-campus"
                  value={placementCampusId}
                  disabled={collegeChoices.isPending || collegeChoices.isError}
                  onChange={(event) => {
                    setPlacementCampusId(event.target.value);
                    setPlacementCollegeId("");
                    setPlacementError(null);
                  }}
                >
                  <option value="">Not assigned</option>
                  {campuses.map((campus) => (
                    <option key={campus.id} value={campus.id}>
                      {campus.code} · {campus.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className={fieldClass}>
                <Label htmlFor="create-student-college">College</Label>
                <Select
                  id="create-student-college"
                  value={placementCollegeId}
                  disabled={!placementCampusId || collegeChoices.isPending || collegeChoices.isError}
                  onChange={(event) => {
                    setPlacementCollegeId(event.target.value);
                    setPlacementError(null);
                  }}
                >
                  <option value="">
                    {placementCampusId ? "Select a College" : "Select a Campus first"}
                  </option>
                  {placementColleges.map((college) => (
                    <option key={college.id} value={college.id}>
                      {college.code} · {college.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            {placementError ? <p role="alert" className="text-sm text-danger">{placementError}</p> : null}
          </fieldset>
        ) : null}
        <label className="flex items-center gap-3 text-sm font-medium text-ink">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(event) => change("is_active", event.target.checked)}
            className="size-4 accent-brand"
          />
          Active account
        </label>
        <ManagedActionFeedback action={action} showMessages={!review} />
        </PanelBody>
        <PanelFooter>
          <Button type="submit" disabled={create.isPending}>
            Review account
          </Button>
          <Link
            href="/portal/accounts"
            className="inline-flex min-h-10 items-center px-3 text-sm font-semibold text-muted hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Cancel
          </Link>
        </PanelFooter>
      </form>
      </Panel>
      <ConsequentialActionDialog
        open={review !== null}
        title={review ? `Create account for ${reviewName}?` : "Create account?"}
        confirmLabel="Create account"
        pendingLabel="Creating account…"
        pending={create.isPending}
        error={action.error}
        onOpenChange={(open) => {
          if (!open) setReview(null);
        }}
        onConfirm={() => void confirmCreate()}
      >
        {review ? (
          <>
            <p>Review the account that will be created.</p>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted">Name</dt>
                <dd className="font-semibold text-ink">{reviewName}</dd>
              </div>
              <div>
                <dt className="text-muted">Institutional ID</dt>
                <dd className="font-semibold text-ink">{review.institutional_id}</dd>
              </div>
              <div>
                <dt className="text-muted">Email</dt>
                <dd className="break-words font-semibold text-ink">{review.email}</dd>
              </div>
              <div>
                <dt className="text-muted">Role</dt>
                <dd className="font-semibold text-ink">{roleLabels[review.role]}</dd>
              </div>
              <div>
                <dt className="text-muted">Account status</dt>
                <dd className="font-semibold text-ink">
                  {review.is_active ? "Active" : "Disabled"}
                </dd>
              </div>
              {review.role === RoleCode.STUDENT ? (
                <div>
                  <dt className="text-muted">Initial academic placement</dt>
                  <dd className="font-semibold text-ink">
                    {review.student_college_id && reviewedCampus && reviewedCollege
                      ? `${reviewedCampus.name} · ${reviewedCollege.name}`
                      : "Not assigned"}
                  </dd>
                </div>
              ) : null}
            </dl>
            <p>
              {review.is_active
                ? "This account will be active after creation."
                : "This account will be created disabled and cannot sign in until enabled."}
            </p>
            {review.role === RoleCode.FACULTY ? <p>Faculty home College: {selectedFacultyCollege ? `${selectedFacultyCollege.campus_name} · ${selectedFacultyCollege.name}` : review.faculty_college_id ? "Selected College is no longer available" : "Not assigned"}. Digital Referrals are not available.</p> : null}
            {review.role === RoleCode.STUDENT ? (
              <p>New Student accounts start with current Student status.</p>
            ) : null}
            {review.role === RoleCode.STUDENT && review.student_college_id ? (
              <p>Initial academic placement is recorded as unverified and does not confirm enrollment.</p>
            ) : null}
          </>
        ) : null}
      </ConsequentialActionDialog>
    </section>
  );
}
