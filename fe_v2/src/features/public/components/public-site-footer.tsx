import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { PUBLIC_FOOTER_GROUPS, PUBLIC_SITE } from "@/features/public/config";
import { PublicAccountLink } from "@/features/public/components/public-account-link";
import { PublicBrand } from "@/features/public/components/public-brand";

export function PublicSiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="public-footer">
      <div className="public-shell public-footer__inner">
        <div className="public-footer__identity">
          <PublicBrand footer />
          <p className="public-footer__institution-copy">
            Updates, resources, and support from the {PUBLIC_SITE.office} at {PUBLIC_SITE.institution}.
          </p>
          <Link className="public-footer__cta" href="/contact">
            Contact the office
            <ArrowUpRight aria-hidden="true" />
          </Link>
        </div>

        <div className="public-footer__details">
          <div className="public-footer__link-groups">
            {PUBLIC_FOOTER_GROUPS.map((group) => (
              <nav key={group.title} className="public-footer__link-group" aria-label={group.title}>
                <h2>{group.title}</h2>
                <ul>
                  {group.links.map((link) => (
                    <li key={link.href}>
                      {link.href === PUBLIC_SITE.accountHref ? (
                        <PublicAccountLink
                          signedInLabel="Open workspace"
                          signedOutLabel={link.label}
                        />
                      ) : (
                        <Link href={link.href}>{link.label}</Link>
                      )}
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </div>
      </div>

      <div className="public-shell public-footer__meta">
        <p>© {year} {PUBLIC_SITE.institution}</p>
        <p>{PUBLIC_SITE.office}</p>
      </div>
    </footer>
  );
}
