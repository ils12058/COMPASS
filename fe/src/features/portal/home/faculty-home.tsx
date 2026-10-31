import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import type { UserSummary } from "@/lib/api/generated/model";

export function FacultyHome({ user }: { user: UserSummary }) {
  const affiliation = user.faculty_affiliation;
  return (
    <section aria-labelledby="faculty-home-heading" className="max-w-2xl">
      <PageHeader title="Faculty" headingId="faculty-home-heading" />
      <Panel>
        <PanelBody className="space-y-4 text-sm">
          <p>Your Faculty account is active. Digital Student Referrals are not available yet.</p>
          <dl>
            <dt className="text-muted">Home College</dt>
            <dd className="mt-1 font-medium">{affiliation?.college_name ? `${affiliation.campus_name} · ${affiliation.college_name}` : "Not assigned"}</dd>
          </dl>
          {!affiliation?.active ? <p>Contact the account administrator to confirm your institutional affiliation.</p> : null}
        </PanelBody>
      </Panel>
    </section>
  );
}
