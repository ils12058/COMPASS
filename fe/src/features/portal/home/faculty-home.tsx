"use client";

import type { ReactNode } from "react";
import { Bell, Forward, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageActionLink } from "@/components/ui/page-action";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { pageSheetWidth } from "@/components/ui/page-width";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { facultyReferralAccess, facultySubmissionAvailable, facultySubmitPath } from "@/features/faculty-referrals/access";
import { useFacultyAvailability } from "@/features/faculty-referrals/availability";
import { FacultySubmissionList } from "@/features/faculty-referrals/records";
import { FacultyLoading } from "@/features/faculty-referrals/shared";
import type { FacultyReferralAvailability, UserSummary } from "@/lib/api/generated/model";

export function FacultyHome({ user }: { user: UserSummary }) {
  const query = useFacultyAvailability(user);
  return <FacultyHomeView user={user} availability={query.availability}>
    {query.isPending ? <FacultyLoading label="Checking Referral availability…" /> : query.isError ? <Panel><PanelMessage role="alert" action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>Referral availability could not be checked. No submission is available until this check succeeds.</PanelMessage></Panel> : query.availability?.can_view_submissions && facultyReferralAccess(user).read ? <FacultySubmissionList recent /> : <Panel><PanelHeader title="Digital Referrals" /><PanelMessage>Digital Student Referrals are not available yet.</PanelMessage></Panel>}
  </FacultyHomeView>;
}

export function FacultyHomeView({ user, availability, children }: { user: UserSummary; availability?: FacultyReferralAvailability; children: ReactNode }) {
  const home = user.faculty_affiliation;
  return <section className={`${pageSheetWidth} @container/faculty-home`} aria-labelledby="faculty-home-heading">
    <PageHeader title="Faculty Home" headingId="faculty-home-heading" description={`Welcome, ${user.first_name || "Faculty"}.`} actions={facultyReferralAccess(user).submit && facultySubmissionAvailable(availability) ? <PageActionLink href={facultySubmitPath} label="Submit Referral" icon={Forward} /> : undefined} />
    <div className="grid items-start gap-5 @[54rem]/faculty-home:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      <div className="min-w-0">{children}</div>
      <Panel><PanelHeader title="Your Faculty account" /><PanelBody className="space-y-4 text-sm">
        <dl><dt className="text-muted">Home College</dt><dd className="mt-1 font-medium [overflow-wrap:anywhere]">{home?.college_name ? `${home.campus_name} · ${home.college_name}` : "Not assigned"}</dd></dl>
        {!home?.active ? <p className="text-muted">Contact the account administrator to confirm your institutional affiliation.</p> : null}
        <nav aria-label="Your account" className="flex flex-wrap gap-x-5 gap-y-1">
          <GuardedPortalLink href="/portal/notifications" className="inline-flex min-h-11 items-center gap-2 font-semibold text-brand underline-offset-4 hover:underline"><Bell size={18} aria-hidden="true" />Notifications</GuardedPortalLink>
          <GuardedPortalLink href="/portal/account/profile" className="inline-flex min-h-11 items-center gap-2 font-semibold text-brand underline-offset-4 hover:underline"><UserRound size={18} aria-hidden="true" />My Profile</GuardedPortalLink>
        </nav>
      </PanelBody></Panel>
    </div>
  </section>;
}
