import { Building2 } from "lucide-react";

import { PersonAvatar } from "@/features/account/components/person-avatar";
import {
  threadCounselorIdentity,
  threadUsesOfficeIdentity,
  type GuidanceViewer,
} from "@/features/guidance-messages/guidance-messages-presentation";
import type { GuidanceThreadResponse } from "@/lib/api/generated/model";

/** An office represents the shared recipient; people use the existing avatar, with a photo when sent. */
export function GuidanceIdentityAvatar({
  name,
  office = false,
  photoUrl,
  photoUpdatedAt,
}: {
  name: string;
  office?: boolean;
  photoUrl?: string | null;
  photoUpdatedAt?: string | null;
}) {
  return office ? (
    <span aria-hidden="true" className="inline-flex size-8 shrink-0 items-center justify-center text-muted">
      <Building2 className="size-5" />
    </span>
  ) : <PersonAvatar displayName={name} photoUrl={photoUrl} photoUpdatedAt={photoUpdatedAt} size="compact" />;
}

export function ConversationIdentityAvatar({
  thread, viewer, title,
}: { thread: GuidanceThreadResponse; viewer: GuidanceViewer; title: string }) {
  const counselor = threadCounselorIdentity(thread, viewer);
  return (
    <GuidanceIdentityAvatar
      name={title}
      office={threadUsesOfficeIdentity(thread, viewer)}
      photoUrl={counselor?.profile_photo_url}
      photoUpdatedAt={counselor?.profile_photo_updated_at}
    />
  );
}
