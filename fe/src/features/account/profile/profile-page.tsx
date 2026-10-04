"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";

import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { AccountAvatar, accountDisplayName } from "@/features/account/components/account-avatar";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { accountErrorMessage } from "@/features/account/components/account-errors";
import { userRoleLabel } from "@/features/portal/components/portal-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import type { MyProfilePhotoResponse, MyProfileResponse, MyProfileUpdateRequest } from "@/lib/api/generated/model";
import {
  getProfileGetMyProfileQueryKey,
  profileGetMyProfile,
  useProfileGetMyProfile,
  useProfileRemoveMyPhoto,
  useProfileSetMyPhoto,
  useProfileUpdateMyProfile,
} from "@/lib/api/generated/profile/profile";

function formValues(profile: MyProfileResponse): Required<MyProfileUpdateRequest> {
  return {
    date_of_birth: profile.date_of_birth,
    civil_status: profile.civil_status,
    contact_number: profile.contact_number,
    current_address: profile.current_address,
    permanent_address: profile.permanent_address,
  };
}

// The account's read-only identity and its photo controls. Beside the editable details on wide
// layouts, above them on narrow ones.
function ProfileIdentity({
  profile,
  onAttempt,
  onSaved,
}: {
  profile: MyProfileResponse;
  onAttempt: () => void;
  onSaved: (message: string) => void;
}) {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const upload = useProfileSetMyPhoto();
  const remove = useProfileRemoveMyPhoto();
  const [error, setError] = useState<string | null>(null);
  const pending = upload.isPending || remove.isPending;

  function updatePhoto(photo: MyProfilePhotoResponse) {
    queryClient.setQueryData<Awaited<ReturnType<typeof profileGetMyProfile>>>(
      getProfileGetMyProfileQueryKey(),
      (cached) => cached ? { ...cached, data: { ...cached.data, ...photo } } : cached,
    );
    void queryClient.invalidateQueries({ queryKey: getProfileGetMyProfileQueryKey() });
  }

  async function uploadPhoto(file: File) {
    setError(null);
    onAttempt();
    try {
      const response = await upload.mutateAsync({ data: { photo: file } });
      updatePhoto(response.data);
      onSaved("Profile photo updated.");
    } catch (caught) {
      setError(accountErrorMessage(caught, "The profile photo could not be updated. Please try again."));
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removePhoto() {
    setError(null);
    onAttempt();
    try {
      const response = await remove.mutateAsync();
      updatePhoto(response.data);
      onSaved("Profile photo removed.");
    } catch (caught) {
      setError(accountErrorMessage(caught, "The profile photo could not be removed. Please try again."));
    }
  }

  return (
    <div className="flex items-start gap-4 border-b border-brand-line px-4 py-5 sm:px-5 @[48rem]/profile:flex-col @[48rem]/profile:border-b-0 @[48rem]/profile:border-r">
      <AccountAvatar user={user} profile={profile} size="profile" />
      <div className="min-w-0 flex-1 @[48rem]/profile:w-full">
        <p className="break-words font-heading text-lg font-semibold leading-snug text-ink">{accountDisplayName(user, profile)}</p>
        <dl className="mt-1 space-y-0.5 text-sm text-muted">
          {profile.institutional_id ? (
            <div><dt className="sr-only">Institutional ID</dt><dd>{profile.institutional_id}</dd></div>
          ) : null}
          <div><dt className="sr-only">Role</dt><dd>{userRoleLabel(profile.role)}</dd></div>
          <div><dt className="sr-only">Sign-in email</dt><dd className="break-all">{profile.email}</dd></div>
        </dl>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" disabled={pending} onClick={() => fileInput.current?.click()}>
            {upload.isPending ? "Uploading…" : "Change photo"}
          </Button>
          {profile.profile_photo_url ? (
            <Button variant="quiet" disabled={pending} onClick={() => void removePhoto()}>
              {remove.isPending ? "Removing…" : "Remove photo"}
            </Button>
          ) : null}
        </div>
        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          aria-label="Choose profile photo"
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void uploadPhoto(file);
          }}
        />
        {error ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
      </div>
    </div>
  );
}

function ProfileEditor({
  profile,
  onAttempt,
  onSaved,
}: {
  profile: MyProfileResponse;
  onAttempt: () => void;
  onSaved: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const update = useProfileUpdateMyProfile();
  const [values, setValues] = useState(() => formValues(profile));
  const [saved, setSaved] = useState(() => formValues(profile));
  const [error, setError] = useState<string | null>(null);
  const dirty = JSON.stringify(values) !== JSON.stringify(saved);

  useUnsavedChangesGuard({
    dirty,
    message: "Discard your unsaved profile changes?",
  });


  function setField<K extends keyof Required<MyProfileUpdateRequest>>(field: K, value: Required<MyProfileUpdateRequest>[K]) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dirty) return;
    setError(null);
    // A confirmation from an earlier save must not sit beside this attempt's outcome.
    onAttempt();
    try {
      const response = await update.mutateAsync({ data: values });
      const next = formValues(response.data);
      queryClient.setQueryData(getProfileGetMyProfileQueryKey(), response);
      setValues(next);
      setSaved(next);
      onSaved("Profile changes saved.");
    } catch (caught) {
      setError(accountErrorMessage(caught, "Your profile could not be saved. Please try again."));
    }
  }

  return (
    <form onSubmit={save} className="min-w-0">
      <PanelSection title="Personal information" titleId="personal-heading">
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="date-of-birth">Date of birth</Label>
            <Input id="date-of-birth" type="date" value={values.date_of_birth ?? ""} onChange={(event) => setField("date_of_birth", event.target.value || null)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="civil-status">Civil status</Label>
            <Input id="civil-status" value={values.civil_status} onChange={(event) => setField("civil_status", event.target.value)} />
          </div>
        </div>
      </PanelSection>
      <PanelSection title="Contact information" titleId="contact-heading">
        <div className="grid max-w-md gap-2">
          <Label htmlFor="contact-number">Contact number</Label>
          <Input id="contact-number" type="tel" value={values.contact_number} onChange={(event) => setField("contact_number", event.target.value)} />
        </div>
      </PanelSection>
      <PanelSection title="Address" titleId="address-heading">
        <div className="grid gap-5">
          <div className="grid gap-2">
            <Label htmlFor="current-address">Current address</Label>
            <Input id="current-address" value={values.current_address} onChange={(event) => setField("current_address", event.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="permanent-address">Permanent address</Label>
            <Input id="permanent-address" value={values.permanent_address} onChange={(event) => setField("permanent_address", event.target.value)} />
          </div>
        </div>
      </PanelSection>
      <PanelFooter className="justify-end @[48rem]/profile:rounded-bl-none">
        {error ? <p id="profile-error" role="alert" className="mr-auto text-sm text-danger">{error}</p> : null}
        <Button type="submit" disabled={!dirty || update.isPending} aria-describedby={error ? "profile-error" : undefined}>
          {update.isPending ? "Saving…" : "Save changes"}
        </Button>
      </PanelFooter>
    </form>
  );
}

export function ProfilePage() {
  const profile = useProfileGetMyProfile({ query: { retry: false } });
  const status = useActionStatus();

  return (
    <section aria-labelledby="profile-heading" className="@container/profile">
      <PageHeader title="Profile" headingId="profile-heading" />
      {profile.isPending ? <RowsSkeleton label="Loading profile…" rows={4} framed /> : null}
      {profile.isError ? (
        <Notice
          role="alert"
          tone="danger"
          action={<Button variant="secondary" onClick={() => void profile.refetch()}>Retry</Button>}
        >
          Your profile could not be loaded.
        </Notice>
      ) : null}
      {profile.isSuccess ? (
        // One surface: the read-only identity beside the one form of editable details.
        <Panel as="div" className="grid @[48rem]/profile:grid-cols-[minmax(14rem,18rem)_minmax(0,1fr)]">
          <ProfileIdentity profile={profile.data.data} onAttempt={status.dismiss} onSaved={status.show} />
          <ProfileEditor profile={profile.data.data} onAttempt={status.dismiss} onSaved={status.show} />
        </Panel>
      ) : null}
      <ActionStatus status={status.status} onDismiss={status.dismiss} />
    </section>
  );
}
