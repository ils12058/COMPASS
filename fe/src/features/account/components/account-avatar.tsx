"use client";

import Image from "next/image";
import { useState } from "react";

import { userDisplayName } from "@/features/portal/components/portal-presentation";
import type { MyProfileResponse, UserSummary } from "@/lib/api/generated/model";

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
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const photoUrl = profile?.profile_photo_url;
  const dimension = size === "profile" ? 72 : 40;

  return (
    <span
      aria-hidden="true"
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-support-soft font-heading font-bold text-support-strong ${size === "profile" ? "size-[4.5rem] text-xl" : "size-10 text-sm"}`}
    >
      {photoUrl && failedUrl !== photoUrl ? (
        <Image
          src={photoUrl}
          alt=""
          width={dimension}
          height={dimension}
          unoptimized
          className="size-full object-cover"
          onError={() => setFailedUrl(photoUrl)}
        />
      ) : accountInitials(user, profile)}
    </span>
  );
}
