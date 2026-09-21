export function NotificationPagination({
  page,
  hasNext,
  pending,
  onPrevious,
  onNext,
}: {
  page: number;
  hasNext: boolean;
  pending: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <nav className="flex items-center justify-between gap-4" aria-label="Notification pages">
      <button
        type="button"
        disabled={page <= 1 || pending}
        onClick={onPrevious}
        className="min-h-10 rounded-lg border bg-card px-4 py-2 text-sm font-semibold disabled:opacity-50"
      >
        Previous
      </button>
      <span className="text-sm text-muted-foreground">Page {page}</span>
      <button
        type="button"
        disabled={!hasNext || pending}
        onClick={onNext}
        className="min-h-10 rounded-lg border bg-card px-4 py-2 text-sm font-semibold disabled:opacity-50"
      >
        Next
      </button>
    </nav>
  );
}
