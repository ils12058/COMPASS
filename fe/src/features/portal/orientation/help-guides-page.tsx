"use client";

import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader, PanelSection } from "@/components/ui/panel";
import { pageSheetWidth } from "@/components/ui/page-width";
import { usePortalOrientation } from "./portal-orientation";

export function HelpGuidesPage() {
  const { launch, preference, guides, preferences, launchTask } = usePortalOrientation();
  const groups = [...new Set(guides.map(guide => guide.group))];
  return <section aria-labelledby="help-guides-heading" className={pageSheetWidth}>
    <PageHeader title="Help & guides" headingId="help-guides-heading" />
    <Panel aria-labelledby="orientation-guide-heading">
      <PanelHeader title="Getting around COMPASS" titleId="orientation-guide-heading" />
      <PanelBody className="space-y-3">
        <p className="text-sm leading-6 text-muted">A short guide to Home, navigation, and the portal bar. Opens on Home; you can exit at any time.</p>
        {preference === "completed" ? <p className="text-sm text-muted">Completed in this browser.</p> : null}
        <Button onClick={event => launch(event.currentTarget)}>{preference === "completed" ? "Replay guide" : "Start guide"}</Button>
      </PanelBody>
      {groups.map((group, index) => <PanelSection key={group} title={group} titleId={`task-guide-group-${index}`}>
        <ul className="divide-y divide-border">
          {guides.filter(guide => guide.group === group).map(guide => <li key={guide.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
            <div className="min-w-0 flex-[1_1_15rem]"><h3 className="text-sm font-semibold text-ink">{guide.title}</h3>
              <p className="mt-1 text-sm text-muted">{guide.steps.length} steps{preferences[guide.id] === "completed" ? " · Completed in this browser" : ""}</p>
            </div>
            <Button variant="secondary" data-guide-catalog={guide.id} aria-label={`${preferences[guide.id] === "completed" ? "Replay" : "Start"}: ${guide.title}`} onClick={event => launchTask(guide.id, event.currentTarget, true)}>
              {preferences[guide.id] === "completed" ? "Replay" : "Start"}
            </Button>
          </li>)}
        </ul>
      </PanelSection>)}
    </Panel>
    <p className="mt-4 text-sm leading-6 text-muted">Completion is saved only in this browser.</p>
  </section>;
}
