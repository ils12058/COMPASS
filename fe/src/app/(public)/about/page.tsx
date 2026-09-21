import Image from "next/image";
import type { Metadata } from "next";

import { PUBLIC_SITE } from "@/features/public/config";

export const metadata: Metadata = {
  title: "About",
};

export default function AboutPage() {
  return (
    <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-5 py-12 sm:px-8 lg:grid-cols-[1fr_0.45fr]">
      <section className="space-y-5">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">{PUBLIC_SITE.office}</p>
        <h1 className="font-heading text-4xl font-bold tracking-tight">About COMPASS</h1>
        <p className="max-w-3xl text-lg leading-8 text-muted-foreground">
          COMPASS stands for Counseling Office Management Platform and Student Services. It is the
          digital platform used to support Guidance and Counseling Office services at the
          University of Camarines Norte.
        </p>
        <p className="max-w-3xl leading-7 text-foreground/85">
          These public pages share office announcements and curated resources. Signed-in users can
          open COMPASS to view the services and account features available to them.
        </p>
      </section>

      <div className="relative mx-auto h-72 w-full max-w-sm" aria-hidden="true">
        <Image
          src="/illustrations/gco-character-point-up.png"
          alt=""
          fill
          sizes="35vw"
          className="object-contain object-bottom"
        />
      </div>
    </div>
  );
}
