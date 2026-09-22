import Image from "next/image";
import Link from "next/link";

const START_ITEMS = [
  {
    title: "Explore Guidance services",
    body: "Learn what COMPASS connects you to, then sign in to see the options available to your account.",
    href: "/services",
    link: "Explore support",
  },
  {
    title: "Read office updates",
    body: "See public announcements shared by the Guidance and Counseling Office.",
    href: "/announcements",
    link: "View announcements",
  },
  {
    title: "Find guidance resources",
    body: "Browse public articles, links, and downloadable materials curated for the university community.",
    href: "/resources",
    link: "Browse resources",
  },
] as const;

export function HomepageStart() {
  return (
    <section className="mx-auto grid w-full max-w-7xl gap-8 px-5 py-12 sm:px-8 lg:grid-cols-[0.35fr_1fr]">
      <div className="relative mx-auto hidden min-h-72 w-full max-w-xs lg:block" aria-hidden="true">
        <Image
          src="/illustrations/gco-character-point-right.png"
          alt=""
          fill
          sizes="25vw"
          className="object-contain object-bottom"
        />
      </div>

      <div>
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">Start here</p>
        <h2 className="mt-1 font-heading text-3xl font-bold">Find what you need</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {START_ITEMS.map((item) => (
            <article key={item.href} className="rounded-xl border bg-card p-5 shadow-sm">
              <h3 className="font-heading text-lg font-bold">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
              <Link href={item.href} className="mt-4 inline-flex text-sm font-semibold">
                {item.link}
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
