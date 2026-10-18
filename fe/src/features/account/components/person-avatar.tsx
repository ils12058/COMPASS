"use client";

import Image from "next/image";
import { useState } from "react";

export type PersonAvatarSize = "compact" | "standard" | "large";

const sizeStyles: Record<PersonAvatarSize, { className: string; dimension: number }> = {
  compact: { className: "size-8 text-xs", dimension: 32 },
  standard: { className: "size-10 text-sm", dimension: 40 },
  large: { className: "size-[4.5rem] text-xl", dimension: 72 },
};

const titles = new Set(["mr", "mrs", "ms", "miss", "dr", "prof", "rev"]);
const suffixes = new Set(["jr", "sr", "ii", "iii", "iv", "phd", "edd", "md", "mba"]);

function tokensFromDisplayName(displayName: string): string[] {
  const name = displayName.trim();
  if (!name) return [];

  const [left, right] = name.split(",", 2).map((part) => part.trim());
  const rightToken = right?.replace(/[.]/g, "").toLocaleLowerCase();
  // A comma before a credential or suffix does not make the name family-first.
  const ordered = right && !suffixes.has(rightToken ?? "") ? `${right} ${left}` : left;
  return ordered
    .split(/\s+/)
    .filter(Boolean)
    .filter((part) => {
      const token = part.replace(/[.]/g, "").toLocaleLowerCase();
      return !titles.has(token) && !suffixes.has(token);
    });
}

export function personInitials(displayName: string): string {
  const tokens = tokensFromDisplayName(displayName);
  const first = tokens[0] ? Array.from(tokens[0])[0] : undefined;
  const second = tokens.length > 1 ? Array.from(tokens[1])[0] : undefined;
  return `${first ?? "?"}${second ?? ""}`.toLocaleUpperCase();
}

export function personPhotoKey(photoUrl?: string | null, photoUpdatedAt?: string | null): string | null {
  return photoUrl ? `${photoUrl}\u0000${photoUpdatedAt ?? ""}` : null;
}

export function PersonAvatar({
  displayName,
  initials,
  photoUrl,
  photoUpdatedAt,
  size = "standard",
}: {
  displayName: string;
  initials?: string;
  photoUrl?: string | null;
  photoUpdatedAt?: string | null;
  size?: PersonAvatarSize;
}) {
  const [failedPhotoKey, setFailedPhotoKey] = useState<string | null>(null);
  const photoKey = personPhotoKey(photoUrl, photoUpdatedAt);
  const showPhoto = Boolean(photoUrl && photoKey !== failedPhotoKey);
  const { className, dimension } = sizeStyles[size];

  return (
    <span
      aria-hidden="true"
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-support-soft font-heading font-bold text-support-strong ${className}`}
    >
      {showPhoto && photoUrl && photoKey ? (
        <Image
          key={photoKey}
          src={photoUrl}
          alt=""
          width={dimension}
          height={dimension}
          unoptimized
          className="size-full object-cover"
          onError={() => setFailedPhotoKey(photoKey)}
        />
      ) : initials || personInitials(displayName)}
    </span>
  );
}
