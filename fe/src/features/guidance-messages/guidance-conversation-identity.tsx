import { Building2 } from "lucide-react";

import { PersonAvatar } from "@/features/account/components/person-avatar";
import { threadUsesOfficeIdentity, type GuidanceViewer } from "@/features/guidance-messages/guidance-messages-presentation";
import type { GuidanceThreadResponse } from "@/lib/api/generated/model";

/** An office represents the shared recipient; people use the existing initials primitive. */
export function GuidanceIdentityAvatar({ name, office = false }: { name: string; office?: boolean }) {
  return office ? (
    <span aria-hidden="true" className="inline-flex size-8 shrink-0 items-center justify-center text-muted">
      <Building2 className="size-5" />
    </span>
  ) : <PersonAvatar displayName={name} size="compact" />;
}

export function ConversationIdentityAvatar({
  thread, viewer, title,
}: { thread: GuidanceThreadResponse; viewer: GuidanceViewer; title: string }) {
  return <GuidanceIdentityAvatar name={title} office={threadUsesOfficeIdentity(thread, viewer)} />;
}
