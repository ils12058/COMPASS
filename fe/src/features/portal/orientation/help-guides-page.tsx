"use client";

import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { usePortalOrientation } from "./portal-orientation";

export function HelpGuidesPage() {
  const { launch, preference } = usePortalOrientation();
  return <section aria-labelledby="help-guides-heading">
    <PageHeader title="Help & guides" headingId="help-guides-heading" />
    <Panel aria-labelledby="orientation-guide-heading">
      <PanelHeader title="Getting around COMPASS" titleId="orientation-guide-heading" />
      <PanelBody className="space-y-4">
        <p className="text-sm leading-6 text-muted">A short guide to Home, navigation, and the portal bar. Opens on Home; you can exit at any time.</p>
        {preference === "completed" ? <p className="text-sm text-muted">Completed in this browser.</p> : null}
        <Button onClick={event => launch(event.currentTarget)}>{preference === "completed" ? "Replay guide" : "Start guide"}</Button>
        <p className="text-sm leading-6 text-muted">Completion is saved only in this browser. It does not sync across accounts or devices.</p>
      </PanelBody>
    </Panel>
  </section>;
}
