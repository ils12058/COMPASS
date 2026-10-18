"use client";

import { userDisplayName } from "@/features/portal/components/portal-presentation";
import type { MyProfileResponse, UserSummary } from "@/lib/api/generated/model";

import { PersonAvatar } from "./person-avatar";

export function accountDisplayName(user: UserSummary, profile?: MyProfileResponse): string {
  return profile?.full_name.trim() || userDisplayName(user);
}

export function accountInitials(user: UserSummary, profile?: MyProfileResponse): string {
  const parts = (profile?.full_name.trim() || `${user.first_name} ${user.last_name}`.trim())
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length > 1) return `${parts[0][0]}${parts.at(-1)?.[0] ?? ""}`.toLocaleUpperCase();
  return parts[0]?.[0]?.toLocaleUpperCase() ?? "?";
}

export function AccountAvatar({
  user,
  profile,
  size = "topbar",
}: {
  user: UserSummary;
  profile?: MyProfileResponse;
  size?: "topbar" | "profile";
}) {
  return (
    <PersonAvatar
      displayName={accountDisplayName(user, profile)}
      initials={accountInitials(user, profile)}
      photoUrl={profile?.profile_photo_url}
      photoUpdatedAt={profile?.profile_photo_updated_at}
      size={size === "profile" ? "large" : "standard"}
    />
  );
}
