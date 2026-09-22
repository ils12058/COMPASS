"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AccountAvatar, accountDisplayName } from "@/features/account/components/account-avatar";
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

function ProfilePhoto({ profile }: { profile: MyProfileResponse }) {
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
    try {
      const response = await upload.mutateAsync({ data: { photo: file } });
      updatePhoto(response.data);
    } catch (caught) {
      setError(accountErrorMessage(caught, "The profile photo could not be updated. Please try again."));
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removePhoto() {
    setError(null);
    try {
      const response = await remove.mutateAsync();
      updatePhoto(response.data);
    } catch (caught) {
      setError(accountErrorMessage(caught, "The profile photo could not be removed. Please try again."));
    }
  }

  return (
    <div className="flex flex-col gap-5 border-b border-border pb-8 sm:flex-row sm:items-center">
      <AccountAvatar user={user} profile={profile} size="profile" />
      <div className="min-w-0 flex-1">
        <p className="font-heading text-2xl font-semibold text-ink">{accountDisplayName(user, profile)}</p>
        {profile.institutional_id ? <p className="mt-1 text-sm text-muted">{profile.institutional_id}</p> : null}
        <p className="mt-1 text-sm text-muted">{userRoleLabel(profile.role)}</p>
        <p className="mt-1 break-all text-sm text-muted">{profile.email}</p>
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

function ProfileEditor({ profile }: { profile: MyProfileResponse }) {
  const queryClient = useQueryClient();
  const update = useProfileUpdateMyProfile();
  const [values, setValues] = useState(() => formValues(profile));
  const [saved, setSaved] = useState(() => formValues(profile));
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const dirty = JSON.stringify(values) !== JSON.stringify(saved);

  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const guardLink = (event: MouseEvent) => {
      if (!(event.target instanceof Element)) return;
      const anchor = event.target.closest("a[href]");
      if (!anchor || !(anchor instanceof HTMLAnchorElement)) return;
      if (anchor.origin === window.location.origin && anchor.pathname === window.location.pathname) return;
      if (!window.confirm("Discard your unsaved profile changes?")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", guardLink, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", guardLink, true);
    };
  }, [dirty]);

  function setField<K extends keyof Required<MyProfileUpdateRequest>>(field: K, value: Required<MyProfileUpdateRequest>[K]) {
    setValues((current) => ({ ...current, [field]: value }));
    setSuccess(false);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dirty) return;
    setError(null);
    try {
      const response = await update.mutateAsync({ data: values });
      const next = formValues(response.data);
      queryClient.setQueryData(getProfileGetMyProfileQueryKey(), response);
      setValues(next);
      setSaved(next);
      setSuccess(true);
    } catch (caught) {
      setError(accountErrorMessage(caught, "Your profile could not be saved. Please try again."));
    }
  }

  return (
    <form className="mt-8 space-y-8" onSubmit={save}>
      <section aria-labelledby="personal-heading">
        <h2 id="personal-heading" className="font-heading text-xl font-semibold text-ink">Personal information</h2>
        <div className="mt-4 grid gap-5 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="date-of-birth">Date of birth</Label>
            <Input id="date-of-birth" type="date" value={values.date_of_birth ?? ""} onChange={(event) => setField("date_of_birth", event.target.value || null)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="civil-status">Civil status</Label>
            <Input id="civil-status" value={values.civil_status} onChange={(event) => setField("civil_status", event.target.value)} />
          </div>
        </div>
      </section>
      <section aria-labelledby="contact-heading" className="border-t border-border pt-7">
        <h2 id="contact-heading" className="font-heading text-xl font-semibold text-ink">Contact information</h2>
        <div className="mt-4 grid max-w-md gap-2">
          <Label htmlFor="contact-number">Contact number</Label>
          <Input id="contact-number" type="tel" value={values.contact_number} onChange={(event) => setField("contact_number", event.target.value)} />
        </div>
      </section>
      <section aria-labelledby="address-heading" className="border-t border-border pt-7">
        <h2 id="address-heading" className="font-heading text-xl font-semibold text-ink">Address</h2>
        <div className="mt-4 grid gap-5">
          <div className="grid gap-2">
            <Label htmlFor="current-address">Current address</Label>
            <Input id="current-address" value={values.current_address} onChange={(event) => setField("current_address", event.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="permanent-address">Permanent address</Label>
            <Input id="permanent-address" value={values.permanent_address} onChange={(event) => setField("permanent_address", event.target.value)} />
          </div>
        </div>
      </section>
      {error ? <p id="profile-error" role="alert" className="text-sm text-danger">{error}</p> : null}
      {success ? <p role="status" className="text-sm text-success">Profile changes saved.</p> : null}
      <div className="flex justify-end border-t border-border pt-6">
        <Button type="submit" disabled={!dirty || update.isPending} aria-describedby={error ? "profile-error" : undefined}>
          {update.isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}

export function ProfilePage() {
  const profile = useProfileGetMyProfile({ query: { retry: false } });

  return (
    <section aria-labelledby="profile-heading">
      <h1 id="profile-heading" className="font-heading text-3xl font-bold text-ink">Profile</h1>
      {profile.isPending ? <p className="mt-8 text-sm text-muted" role="status">Loading profile…</p> : null}
      {profile.isError ? (
        <div className="mt-8 border-t border-border pt-6" role="alert">
          <p className="text-sm text-danger">Your profile could not be loaded.</p>
          <Button variant="secondary" className="mt-4" onClick={() => void profile.refetch()}>Retry</Button>
        </div>
      ) : null}
      {profile.isSuccess ? (
        <div className="mt-7">
          <ProfilePhoto profile={profile.data.data} />
          <ProfileEditor profile={profile.data.data} />
        </div>
      ) : null}
    </section>
  );
}
