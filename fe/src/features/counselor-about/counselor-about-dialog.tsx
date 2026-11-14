"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { IconAction } from "@/components/ui/icon-action";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import {
  ABOUT_ASSIGNMENTS_HEADING,
  ABOUT_EMPTY_COPY,
  aboutCampusRows,
  aboutError,
} from "@/features/counselor-about/counselor-about-presentation";
import { useOrganizationGetCounselorAbout } from "@/lib/api/generated/organization/organization";
import { cn } from "@/lib/utils/cn";

/**
 * Opens the shared Counselor About summary. It only shows information: it never selects the
 * Counselor, books, or changes the form it sits in (ABOUT-02), so it is always a plain button: an
 * Info icon named "About <Counselor>", with the short label shown for touch.
 */
export function CounselorAboutButton({
  counselorId,
  counselorName,
  className,
  variant = "quiet",
}: {
  counselorId: string;
  counselorName: string;
  className?: string;
  variant?: "quiet" | "secondary";
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <IconAction type="button" action="info" label={`About ${counselorName}`} touchLabel="About" variant={variant} className={cn("shrink-0", className)} data-counselor-about={counselorId} />
      </DialogTrigger>
      {open ? <CounselorAboutContent counselorId={counselorId} counselorName={counselorName} /> : null}
    </Dialog>
  );
}

function CounselorAboutContent({ counselorId, counselorName }: { counselorId: string; counselorName: string }) {
  // Assignments and access change; every opening asks the backend again and keeps no copy.
  const query = useOrganizationGetCounselorAbout(counselorId, {
    query: { retry: false, staleTime: 0, gcTime: 0, refetchOnMount: "always", refetchOnWindowFocus: "always" },
  });
  const about = query.isError ? undefined : query.data?.data;
  const name = about?.counselor.display_name.trim() || counselorName;
  const rows = about ? aboutCampusRows(about) : [];
  const failure = query.isError ? aboutError(query.error) : null;

  return (
    <DialogContent closeLabel="Close Counselor details" aria-busy={query.isFetching}>
      <div className="flex items-center gap-3 pr-8">
        <PersonAvatar
          displayName={name}
          photoUrl={about?.counselor.profile_photo_url}
          photoUpdatedAt={about?.counselor.profile_photo_updated_at}
          size="large"
        />
        <div className="min-w-0">
          <DialogTitle className="pr-0 [overflow-wrap:anywhere]">{name}</DialogTitle>
          <DialogDescription className="mt-0.5">Counselor</DialogDescription>
        </div>
      </div>
      <section aria-labelledby="counselor-about-assignments" className="mt-5">
        <h3 id="counselor-about-assignments" className="text-sm font-semibold text-ink">{ABOUT_ASSIGNMENTS_HEADING}</h3>
        {query.isPending ? (
          <p role="status" className="mt-2 text-sm text-muted">Loading Counselor details…</p>
        ) : failure ? (
          <div role="alert" className="mt-2 text-sm">
            <p className="text-danger">{failure.message}</p>
            {failure.retryable ? (
              <Button className="mt-2" variant="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>
                {query.isFetching ? "Retrying…" : "Retry"}
              </Button>
            ) : null}
          </div>
        ) : rows.length === 0 ? (
          <p className="mt-2 text-sm text-muted">{ABOUT_EMPTY_COPY}</p>
        ) : (
          <div className="mt-2 space-y-3">
            {rows.map((campus) => (
              <div key={campus.id}>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted [overflow-wrap:anywhere]">{campus.name}</p>
                <ul className="mt-1 divide-y divide-border rounded-sm border border-border">
                  {campus.colleges.map((college) => (
                    <li key={college.id} className="px-3 py-2 text-sm text-ink [overflow-wrap:anywhere]">
                      <span className="block">{college.name}</span>
                      {college.note ? <span className="block text-xs text-muted">{college.note}</span> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </DialogContent>
  );
}
