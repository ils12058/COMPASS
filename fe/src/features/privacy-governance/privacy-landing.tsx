"use client";

import { Archive, FileText, ShieldCheck, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { PrivacyPageHeader } from "./privacy-governance-shared";
import {
  canViewPrivacyGovernance,
  canViewRetention,
} from "./privacy-governance-access";

type Workspace = { href: string; title: string; description: string; icon: LucideIcon };

// The governance workspaces this account can open, each a separate destination. Visibility follows
// the same capabilities as the workspace tabs. No counts, scores, or status summaries.
export function PrivacyLanding() {
  const { user } = usePortalSession();
  const governance = canViewPrivacyGovernance(user);
  const workspaces: Workspace[] = [
    ...(governance
      ? [{
          href: "/portal/privacy/notices",
          title: "Privacy Notices",
          description: "Privacy Notices and their revisions.",
          icon: FileText,
        }]
      : []),
    ...(canViewRetention(user)
      ? [{
          href: "/portal/privacy/retention",
          title: "Retention & Disposition",
          description: "Retention rules, disposition cases, and holds.",
          icon: Archive,
        }]
      : []),
    ...(governance
      ? [{
          href: "/portal/privacy/activity",
          title: "Privacy & Security Activity",
          description: "A curated record of privacy-relevant events. It is not the full audit trail.",
          icon: ShieldCheck,
        }]
      : []),
  ];

  return (
    <section>
      <PrivacyPageHeader title="Privacy Governance" />
      <ul className="grid max-w-5xl gap-4 md:grid-cols-2 xl:grid-cols-3">
        {workspaces.map(({ href, title, description, icon: Icon }) => (
          <li key={href} className="flex">
            <Link
              href={href}
              className="group flex w-full items-start gap-3 rounded-sm border border-brand-line bg-surface-raised px-4 py-4 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:px-5"
            >
              <Icon size={20} aria-hidden="true" className="mt-0.5 shrink-0 text-brand" />
              <span className="min-w-0 flex-1">
                <span className="block font-heading text-base font-semibold text-ink group-hover:underline">
                  {title}
                </span>
                <span className="mt-1 block text-sm leading-6 text-muted">{description}</span>
              </span>
              <span aria-hidden="true" className="mt-0.5 font-semibold text-brand">→</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
