import { Badge } from "@/components/ui/badge";
import { isExpired, statusLabel } from "@/features/content/presentation";

export function PublicationStatusBadge({
  status,
  expiresAt,
}: {
  status: string;
  expiresAt?: string | null;
}) {
  const variant =
    status === "PUBLISHED" ? "support" : status === "ARCHIVED" ? "neutral" : "gold";

  return (
    <span className="inline-flex flex-wrap gap-1.5">
      <Badge variant={variant}>{statusLabel(status)}</Badge>
      {status === "PUBLISHED" && isExpired(expiresAt) ? (
        <Badge variant="neutral">Expired</Badge>
      ) : null}
    </span>
  );
}
