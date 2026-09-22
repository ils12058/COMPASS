"use client";

import { type ChangeEvent, type FormEvent, useRef, useState } from "react";
import {
  Camera,
  Check,
  CircleHelp,
  IdCard,
  LockKeyhole,
  Trash2,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { friendlyAuthError } from "@/features/auth/utils/errors";
import { getPortalRoleLabel } from "@/features/portal/portal-identity";
import {
  getProfileGetMyProfileQueryKey,
  useProfileRemoveMyPhoto,
  useProfileSetMyPhoto,
  useProfileUpdateMyProfile,
} from "@/lib/api/generated/profile/profile";
import type { ProfileGetMyProfileQueryResult } from "@/lib/api/generated/profile/profile";
import type {
  MyProfileResponse,
  MyProfileUpdateRequest,
} from "@/lib/api/generated/model";

type ProfileDraft = {
  date_of_birth: string;
  civil_status: string;
  contact_number: string;
  current_address: string;
  permanent_address: string;
};

function getDraft(profile: MyProfileResponse): ProfileDraft {
  return {
    date_of_birth: profile.date_of_birth?.slice(0, 10) ?? "",
    civil_status: profile.civil_status,
    contact_number: profile.contact_number,
    current_address: profile.current_address,
    permanent_address: profile.permanent_address,
  };
}

function getInitials(profile: MyProfileResponse) {
  const initials = [profile.first_name, profile.last_name]
    .map((part) => part.trim().charAt(0))
    .filter(Boolean)
    .join("")
    .slice(0, 2);

  return (initials || profile.email.slice(0, 2)).toUpperCase();
}

function displayValue(value: string | null | undefined) {
  return value?.trim() || "Not provided";
}

function ReadOnlyDetail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
      <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-2 break-words text-sm font-semibold text-foreground">{value}</dd>
    </div>
  );
}

export function PortalAccountProfile({
  error,
  isLoading,
  profile,
}: {
  error: unknown;
  isLoading: boolean;
  profile: MyProfileResponse | undefined;
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [draft, setDraft] = useState<ProfileDraft | null>(
    profile ? getDraft(profile) : null,
  );
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [photoMessage, setPhotoMessage] = useState<string | null>(null);

  const updateProfile = useProfileUpdateMyProfile();
  const setPhoto = useProfileSetMyPhoto();
  const removePhoto = useProfileRemoveMyPhoto();

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) {
      return;
    }

    setSavedMessage(null);

    const changes: MyProfileUpdateRequest = {
      date_of_birth: draft.date_of_birth || null,
      civil_status: draft.civil_status.trim(),
      contact_number: draft.contact_number.trim(),
      current_address: draft.current_address.trim(),
      permanent_address: draft.permanent_address.trim(),
    };

    try {
      const response = await updateProfile.mutateAsync({ data: changes });
      queryClient.setQueryData(getProfileGetMyProfileQueryKey(), response);
      setSavedMessage("Your personal details are up to date.");
    } catch (caught) {
      setSavedMessage(
        friendlyAuthError(caught, "We couldn’t save those details. Please try again."),
      );
    }
  }

  async function handlePhotoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }

    setPhotoMessage(null);
    try {
      const response = await setPhoto.mutateAsync({ data: { photo: file } });
      queryClient.setQueryData<ProfileGetMyProfileQueryResult>(getProfileGetMyProfileQueryKey(), (current) =>
        current
          ? {
              ...current,
              data: {
                ...current.data,
                profile_photo_url: response.data.profile_photo_url,
                profile_photo_updated_at: response.data.profile_photo_updated_at,
              },
            }
          : current,
      );
      setPhotoMessage("Your profile photo has been updated.");
    } catch (caught) {
      setPhotoMessage(
        friendlyAuthError(caught, "We couldn’t update your photo. Please try again."),
      );
    }
  }

  async function handlePhotoRemove() {
    setPhotoMessage(null);
    try {
      const response = await removePhoto.mutateAsync();
      queryClient.setQueryData<ProfileGetMyProfileQueryResult>(getProfileGetMyProfileQueryKey(), (current) =>
        current
          ? {
              ...current,
              data: {
                ...current.data,
                profile_photo_url: response.data.profile_photo_url,
                profile_photo_updated_at: response.data.profile_photo_updated_at,
              },
            }
          : current,
      );
      setPhotoMessage("Your profile photo has been removed.");
    } catch (caught) {
      setPhotoMessage(
        friendlyAuthError(caught, "We couldn’t remove your photo. Please try again."),
      );
    }
  }

  if (isLoading && !profile) {
    return (
      <div className="space-y-5" aria-live="polite">
        <div className="h-56 animate-pulse rounded-3xl bg-card" />
        <div className="h-96 animate-pulse rounded-3xl bg-card" />
      </div>
    );
  }

  if (!profile) {
    return (
      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-6 shadow-sm">
        <CircleHelp aria-hidden="true" className="size-7 text-[var(--compass-brand-maroon)]" />
        <h2 className="mt-4 font-heading text-2xl font-bold">Your profile is unavailable</h2>
        <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
          We couldn’t load these details right now. Your workspace is still available; try opening this page again in a moment.
        </p>
        {error ? (
          <p className="mt-4 text-sm text-destructive" role="alert">
            {friendlyAuthError(error, "Please try again when your connection is ready.")}
          </p>
        ) : null}
      </section>
    );
  }

  const currentDraft = draft ?? getDraft(profile);
  const photoBusy = setPhoto.isPending || removePhoto.isPending;

  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
          <Avatar size="lg" className="size-24 border-4 border-[var(--compass-support-soft)]">
            {profile.profile_photo_url ? (
              <AvatarImage src={profile.profile_photo_url} alt={profile.full_name} />
            ) : null}
            <AvatarFallback className="bg-[var(--compass-brand-maroon)] text-2xl font-bold text-white">
              {getInitials(profile)}
            </AvatarFallback>
          </Avatar>

          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
              Profile photo
            </p>
            <h2 className="mt-2 truncate font-heading text-2xl font-bold">{profile.full_name}</h2>
            <p className="mt-1 break-words text-sm text-muted-foreground">
              Use a clear photo so people can recognize your account.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <input
                ref={fileInputRef}
                id="profile-photo"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={handlePhotoChange}
                disabled={photoBusy}
              />
              <Button
                type="button"
                variant="outline"
                disabled={photoBusy}
                onClick={() => fileInputRef.current?.click()}
              >
                <Camera aria-hidden="true" />
                {setPhoto.isPending ? "Uploading…" : "Change photo"}
              </Button>
              {profile.profile_photo_url ? (
                <Button
                  type="button"
                  variant="ghost"
                  disabled={photoBusy}
                  onClick={() => void handlePhotoRemove()}
                >
                  <Trash2 aria-hidden="true" />
                  {removePhoto.isPending ? "Removing…" : "Remove photo"}
                </Button>
              ) : null}
            </div>
          </div>
        </div>

        {photoMessage ? (
          <p className="mt-5 text-sm text-muted-foreground" role="status" aria-live="polite">
            {photoMessage}
          </p>
        ) : null}
      </section>

      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
            <IdCard aria-hidden="true" className="size-5" />
          </div>
          <div>
            <h2 className="font-heading text-2xl font-bold">Account identity</h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              These details identify your account and are maintained through authorized account processes.
            </p>
          </div>
        </div>

        <dl className="mt-6 grid gap-3 sm:grid-cols-2">
          <ReadOnlyDetail label="Institutional ID" value={displayValue(profile.institutional_id)} />
          <ReadOnlyDetail label="Sign-in email" value={profile.email} />
          <ReadOnlyDetail label="First name" value={profile.first_name} />
          <ReadOnlyDetail label="Middle name" value={displayValue(profile.middle_name)} />
          <ReadOnlyDetail label="Last name" value={profile.last_name} />
          <ReadOnlyDetail label="Suffix" value={displayValue(profile.suffix)} />
          <ReadOnlyDetail label="Role" value={getPortalRoleLabel(profile.role)} />
        </dl>
      </section>

      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
        <div>
          <h2 className="font-heading text-2xl font-bold">Personal information</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            Keep the details people may need when supporting you up to date. Your name, institutional ID, role, and sign-in email stay protected here.
          </p>
        </div>

        <form className="mt-6 space-y-6" onSubmit={(event) => void saveProfile(event)}>
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="profile-date-of-birth">Date of birth</Label>
              <Input
                id="profile-date-of-birth"
                type="date"
                value={currentDraft.date_of_birth}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...(current ?? currentDraft),
                    date_of_birth: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="profile-civil-status">Civil status</Label>
              <Input
                id="profile-civil-status"
                value={currentDraft.civil_status}
                placeholder="Optional"
                onChange={(event) =>
                  setDraft((current) => ({
                    ...(current ?? currentDraft),
                    civil_status: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="profile-contact-number">Contact number</Label>
              <Input
                id="profile-contact-number"
                value={currentDraft.contact_number}
                placeholder="Optional"
                autoComplete="tel"
                onChange={(event) =>
                  setDraft((current) => ({
                    ...(current ?? currentDraft),
                    contact_number: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="profile-current-address">Current address</Label>
              <Textarea
                id="profile-current-address"
                value={currentDraft.current_address}
                placeholder="Optional"
                rows={3}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...(current ?? currentDraft),
                    current_address: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="profile-permanent-address">Permanent address</Label>
              <Textarea
                id="profile-permanent-address"
                value={currentDraft.permanent_address}
                placeholder="Optional"
                rows={3}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...(current ?? currentDraft),
                    permanent_address: event.target.value,
                  }))
                }
              />
            </div>
          </div>

          {savedMessage ? (
            <Alert
              className={
                updateProfile.isError
                  ? "border-destructive/30 text-destructive"
                  : "border-[var(--compass-support)]/30 text-[var(--compass-support-strong)]"
              }
              role={updateProfile.isError ? "alert" : "status"}
            >
              {updateProfile.isError ? null : <Check aria-hidden="true" />}
              <AlertDescription>{savedMessage}</AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-wrap items-center gap-3 border-t border-[var(--compass-border)] pt-5">
            <Button type="submit" disabled={updateProfile.isPending}>
              <LockKeyhole aria-hidden="true" />
              {updateProfile.isPending ? "Saving…" : "Save personal information"}
            </Button>
            <p className="text-xs leading-5 text-muted-foreground">
              Only the editable personal details above are sent when you save.
            </p>
          </div>
        </form>
      </section>
    </div>
  );
}
