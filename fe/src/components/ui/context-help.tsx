"use client";

import { CircleHelp } from "lucide-react";
import { type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

export type HelpSection = { heading: string; content: ReactNode };

// One grouped explanation for a workspace. Current blockers, consent and action consequences
// stay beside their state or decision; Help never substitutes for them. The shared Radix Dialog
// owns keyboard/tap activation, focus trapping, Escape and return focus on every screen size.
export function ContextHelp({
  title,
  sections,
  label = "Help",
}: {
  title: string;
  sections: readonly HelpSection[];
  label?: string;
}) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="quiet" className="min-h-11" aria-label={`${label}: ${title}`}>
          <CircleHelp aria-hidden="true" size={18} />
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl" closeLabel="Close Help">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription className="sr-only">Guidance for this workspace.</DialogDescription>
        <HelpSections sections={sections} />
      </DialogContent>
    </Dialog>
  );
}

export function HelpSections({ sections }: { sections: readonly HelpSection[] }) {
  return (
    <div className="mt-5 space-y-5">
      {sections.map(({ heading, content }) => (
        <section key={heading}>
          <h3 className="font-heading text-base font-semibold text-ink">{heading}</h3>
          <div className="mt-1 text-sm leading-6 text-ink [&_a]:font-semibold [&_a]:text-brand [&_a]:underline [&_a]:underline-offset-4 [&_a]:focus-visible:ring-2 [&_a]:focus-visible:ring-focus">
            {content}
          </div>
        </section>
      ))}
    </div>
  );
}
