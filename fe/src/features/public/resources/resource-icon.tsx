import { BookOpen, ExternalLink, FileDown } from "lucide-react";

import { ResourceKindValue, type ResourceKindValue as ResourceKind } from "@/lib/api/generated/model";

export function ResourceIcon({ kind, size = 22 }: { kind: ResourceKind; size?: number }) {
  if (kind === ResourceKindValue.EXTERNAL_LINK) {
    return <ExternalLink size={size} aria-hidden="true" />;
  }

  if (kind === ResourceKindValue.FILE) {
    return <FileDown size={size} aria-hidden="true" />;
  }

  return <BookOpen size={size} aria-hidden="true" />;
}
