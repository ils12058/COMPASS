import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { PUBLIC_FOOTER_GROUPS, PUBLIC_SITE } from "@/features/public/config";
import { PublicBrand } from "@/features/public/components/public-brand";

export function PublicSiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="public-footer">
      <div className="public-shell public-footer__inner">
        <div className="public-footer__identity">
          <PublicBrand footer />
          <p className="public-footer__institution-copy">
            {PUBLIC_SITE.product} is a service of {PUBLIC_SITE.office} at {PUBLIC_SITE.institution}.
          </p>
          <Link className="public-footer__cta" href="/contact">
            Contact guidance
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
                      <Link href={link.href}>{link.label}</Link>
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
        <p>{PUBLIC_SITE.product} is a service of {PUBLIC_SITE.office}.</p>
        <p>Developed for {PUBLIC_SITE.institution}.</p>
      </div>
    </footer>
  );
}
