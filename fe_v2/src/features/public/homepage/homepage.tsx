import { ArrowDown, ArrowRight, ArrowUpRight } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { LANDING_PAGE, PUBLIC_SITE } from "@/features/public/config";

const CHARACTER_ASSETS = {
  "point-right": {
    src: "/illustrations/gco-character-point-right.png",
    width: 338,
    height: 330,
  },
  "point-up": {
    src: "/illustrations/gco-character-point-up.png",
    width: 330,
    height: 330,
  },
  wave: {
    src: "/illustrations/gco-character-wave.png",
    width: 330,
    height: 330,
  },
} as const;

function Character({
  name,
  className = "",
}: {
  name: keyof typeof CHARACTER_ASSETS;
  className?: string;
}) {
  const asset = CHARACTER_ASSETS[name];

  return (
    <span className={`landing-character ${className}`} aria-hidden="true">
      <Image
        src={asset.src}
        alt=""
        width={asset.width}
        height={asset.height}
        className="landing-character__image"
      />
    </span>
  );
}

function ArrowLink({
  href,
  children,
  className = "",
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link href={href} className={`landing-content-link ${className}`}>
      {children}
      <ArrowUpRight aria-hidden="true" />
    </Link>
  );
}

function PaperSheet({
  children,
  className = "",
  tone = "plain",
}: {
  children: ReactNode;
  className?: string;
  tone?: "paper" | "plain" | "sage";
}) {
  return (
    <div className={`landing-paper-sheet ${className}`} data-tone={tone}>
      {children}
    </div>
  );
}

function StickyNote({
  children,
  tone,
  rotation,
}: {
  children: ReactNode;
  tone: string;
  rotation: string;
}) {
  return (
    <article className="landing-sticky-note" data-tone={tone} data-rotation={rotation}>
      <span className="landing-sticky-note__tape" aria-hidden="true" />
      {children}
    </article>
  );
}

function HomepageHero() {
  const { hero } = LANDING_PAGE;

  return (
    <section className="landing-hero" aria-labelledby="landing-hero-heading">
      <Image
        src="/brand/campus-bg.jpg"
        alt=""
        fill
        priority
        sizes="100vw"
        className="landing-hero__backdrop"
        aria-hidden="true"
      />
      <div className="landing-hero__gradient" aria-hidden="true" />
      <div className="public-shell landing-hero__inner">
        <div className="landing-hero__copy">
          <p className="landing-eyebrow landing-eyebrow--light">{hero.eyebrow}</p>
          <h1 id="landing-hero-heading">
            {hero.title} <span>{hero.highlight}</span>
          </h1>
          <p className="landing-hero__summary">{hero.description}</p>
          <div className="landing-hero__actions">
            <Link className="landing-primary-action" href={hero.primaryAction.href}>
              {hero.primaryAction.label}
              <ArrowUpRight aria-hidden="true" />
            </Link>
            <a
              className="landing-secondary-action landing-secondary-action--light"
              href={hero.secondaryAction.href}
            >
              {hero.secondaryAction.label}
              <ArrowDown aria-hidden="true" />
            </a>
          </div>
        </div>

        <div className="landing-hero__art" aria-hidden="true">
          <Image
            src="/illustrations/gco-characters.png"
            alt=""
            width={721}
            height={339}
            priority
            sizes="(min-width: 1024px) 45vw, 90vw"
          />
        </div>
      </div>
    </section>
  );
}

function HomepageStart() {
  const { start } = LANDING_PAGE;

  return (
    <section
      id="start-here"
      className="public-shell landing-section landing-start"
      aria-labelledby="start-here-heading"
    >
      <div className="landing-start__layout">
        <div className="landing-start__character-frame" aria-hidden="true">
          <Character
            name="point-right"
            className="landing-start__character landing-start__character--point-right"
          />
          <Character
            name="point-up"
            className="landing-start__character landing-start__character--point-up"
          />
        </div>
        <div className="landing-start__content">
          <p className="landing-eyebrow">{start.eyebrow}</p>
          <h2 id="start-here-heading">{start.title}</h2>
          <div className="landing-start__cards">
            {start.items.map((item) => (
              <article key={item.href} className="landing-start__card">
                <h3>{item.title}</h3>
                <p>{item.body}</p>
                <ArrowLink href={item.href}>{item.link}</ArrowLink>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function AnnouncementPreview() {
  const { announcements } = LANDING_PAGE;

  return (
    <section
      className="public-shell landing-section"
      aria-labelledby="announcements-heading"
    >
      <div className="landing-section__heading">
        <div>
          <p className="landing-eyebrow">{announcements.eyebrow}</p>
          <h2 id="announcements-heading">{announcements.title}</h2>
          <p>{announcements.description}</p>
        </div>
        <Link className="landing-heading-link" href={announcements.href}>
          {announcements.link}
          <ArrowRight aria-hidden="true" />
        </Link>
      </div>

      <div className="landing-notes-grid">
        {announcements.items.map((item) => (
          <StickyNote key={item.title} tone={item.tone} rotation={item.rotation}>
            <p className="landing-content-meta">{item.category}</p>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
            <ArrowLink href={item.href}>Read announcement</ArrowLink>
          </StickyNote>
        ))}
      </div>
    </section>
  );
}

function GuidancePreview() {
  const { guidance } = LANDING_PAGE;

  return (
    <section
      className="public-shell landing-section"
      aria-labelledby="guidance-heading"
    >
      <div className="landing-guidance-preview">
        <div>
          <p className="landing-eyebrow">{guidance.eyebrow}</p>
          <h2 id="guidance-heading">{guidance.title}</h2>
          <p>{guidance.description}</p>
        </div>
        <Link
          className="landing-content-link landing-guidance-preview__link"
          href={guidance.href}
        >
          {guidance.link}
          <ArrowRight aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}

function ResourcePreview() {
  const { resources } = LANDING_PAGE;

  return (
    <section className="landing-resources-section" aria-labelledby="resources-heading">
      <div className="public-shell landing-section">
        <div className="landing-section__heading">
          <div>
            <p className="landing-eyebrow">{resources.eyebrow}</p>
            <h2 id="resources-heading">{resources.title}</h2>
            <p>{resources.description}</p>
          </div>
          <Link className="landing-heading-link" href={resources.href}>
            {resources.link}
            <ArrowRight aria-hidden="true" />
          </Link>
        </div>

        <div className="landing-resources-grid">
          {resources.items.map((item) => (
            <PaperSheet key={item.title} tone="plain">
              <p className="landing-content-meta">{item.category}</p>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
              <ArrowLink href={item.href}>View resource</ArrowLink>
            </PaperSheet>
          ))}
        </div>
      </div>
    </section>
  );
}

function OfficeContactSection() {
  const { office } = LANDING_PAGE;

  return (
    <section
      className="public-shell landing-section landing-office"
      aria-labelledby="office-heading"
    >
      <div className="landing-office__panel">
        <div className="landing-office__copy">
          <p className="landing-eyebrow">{office.eyebrow}</p>
          <h2 id="office-heading">{office.title}</h2>
          <p>{office.description}</p>
          <div className="landing-office__actions">
            <Link className="landing-primary-action" href={office.primaryAction.href}>
              {office.primaryAction.label}
              <ArrowUpRight aria-hidden="true" />
            </Link>
            <Link className="landing-secondary-action" href={office.secondaryAction.href}>
              {office.secondaryAction.label}
            </Link>
          </div>
        </div>
        <Character name="wave" className="landing-office__character" />
      </div>
    </section>
  );
}

export function Homepage() {
  return (
    <div className="landing-page">
      <HomepageHero />
      <HomepageStart />
      <AnnouncementPreview />
      <GuidancePreview />
      <ResourcePreview />
      <OfficeContactSection />
      <p className="sr-only">{PUBLIC_SITE.product} public landing page</p>
    </div>
  );
}
