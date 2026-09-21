import { ArrowUpRight, Compass, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

const stack = ["Next.js 16", "TanStack Query", "Tailwind CSS", "TypeScript"];

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center px-6 py-16 lg:px-8">
      <div className="grid w-full gap-12 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
        <section className="space-y-8">
          <div className="flex items-center gap-3 text-sm font-semibold tracking-[0.24em] text-primary uppercase">
            <Compass className="size-5" aria-hidden="true" />
            COMPASS / v2
          </div>
          <div className="max-w-3xl space-y-5">
            <p className="text-sm font-medium tracking-wide text-muted-foreground">
              Counseling Office Management Platform and Student Services
            </p>
            <h1 className="text-5xl leading-[1.05] font-semibold tracking-tight text-foreground sm:text-7xl">
              A calmer starting point for better student support.
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-muted-foreground">
              The new frontend workspace is ready. We can build the next COMPASS
              experience here without disturbing the current application.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm font-medium text-foreground">
            {stack.map((item) => (
              <span
                className={cn(
                  "rounded-full border border-border bg-card px-4 py-2 text-card-foreground shadow-sm",
                )}
                key={item}
              >
                {item}
              </span>
            ))}
          </div>
        </section>

        <aside className="rounded-3xl border border-border bg-card p-7 shadow-md">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <Sparkles className="size-6" aria-hidden="true" />
          </div>
          <div className="mt-8 space-y-3">
            <h2 className="text-xl font-semibold text-card-foreground">
              Workspace ready
            </h2>
            <p className="text-sm leading-6 text-muted-foreground">
              Query caching, shared utilities, Google Fonts, and the editor-ready
              package set are wired into this clean base.
            </p>
          </div>
          <div className="mt-8 flex items-center gap-2 text-sm font-semibold text-primary">
            Start shaping the new experience
            <ArrowUpRight className="size-4" aria-hidden="true" />
          </div>
        </aside>
      </div>
    </main>
  );
}
