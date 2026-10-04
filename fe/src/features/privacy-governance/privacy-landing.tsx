"use client";

import Link from "next/link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { PrivacyPageHeader, textLinkClass } from "./privacy-governance-shared";
import {
  canViewPrivacyGovernance,
  canViewRetention,
} from "./privacy-governance-access";
import { Panel, PanelBody } from "@/components/ui/panel";

export function PrivacyLanding() {
  const { user } = usePortalSession();
  return (
    <section>
      <PrivacyPageHeader title="Privacy Governance" />
      <Panel>
        <PanelBody>
          <ul className="grid gap-4 text-sm">
            {canViewPrivacyGovernance(user) ? (
              <li>
                <Link href="/portal/privacy/notices" className={textLinkClass}>
                  Privacy Notices
                </Link>
              </li>
            ) : null}
            {canViewRetention(user) ? (
              <li>
                <Link
                  href="/portal/privacy/retention"
                  className={textLinkClass}
                >
                  Retention & Disposition
                </Link>
              </li>
            ) : null}
            {canViewPrivacyGovernance(user) ? (
              <li>
                <Link href="/portal/privacy/activity" className={textLinkClass}>
                  Privacy & Security Activity
                </Link>
              </li>
            ) : null}
          </ul>
        </PanelBody>
      </Panel>
    </section>
  );
}
