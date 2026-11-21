"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { CompassApiError } from "@/lib/api/errors";
import { referralsUpdateUrgency, getReferralsGetQueryKey, getReferralsListQueryKey } from "@/lib/api/generated/referrals/referrals";
import { getWorkQueueListQueryKey } from "@/lib/api/generated/work/work";
import { getNotificationsListMineQueryKey, getNotificationsGetUnreadCountQueryKey } from "@/lib/api/generated/notifications/notifications";
import type { ReferralDetailResponse } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

export function ReferralUrgencyControl({ referral, canManage, refreshFailed, refresh }: { referral: ReferralDetailResponse; canManage: boolean; refreshFailed: boolean; refresh: () => Promise<ReferralDetailResponse | undefined> }) {
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const status = useActionStatus();
  async function change() {
    if (busy.current || blocked || refreshFailed) return;
    busy.current = true; setPending(true); setError(""); status.dismiss();
    try {
      await referralsUpdateUrgency(referral.id, { is_urgent: !referral.is_urgent, expected_version: referral.urgency_version ?? 0 });
      await Promise.all([
        client.invalidateQueries({ queryKey: getReferralsListQueryKey() }),
        client.invalidateQueries({ queryKey: getReferralsGetQueryKey(referral.id) }),
        client.invalidateQueries({ queryKey: getWorkQueueListQueryKey() }),
        client.invalidateQueries({ queryKey: getNotificationsListMineQueryKey() }),
        client.invalidateQueries({ queryKey: getNotificationsGetUnreadCountQueryKey() }),
      ]);
      status.show(referral.is_urgent ? "Urgent flag cleared." : "Referral marked urgent.");
    } catch (caught) {
      setBlocked(true);
      const latest = await refresh();
      if (caught instanceof CompassApiError && caught.status === 409) {
        setError(latest ? "The urgent flag changed before your action completed. The latest details are shown. Review them before trying again." : "Couldn't refresh this referral. Refresh before changing the urgent flag.");
        setBlocked(!latest);
      } else {
        setError("The change could not be confirmed. Review the latest referral before trying again.");
      }
    } finally { busy.current = false; setPending(false); }
  }
  return <Panel aria-labelledby="referral-urgency-heading">
    <PanelHeader title="Urgency" titleId="referral-urgency-heading" />
    <PanelBody className="space-y-3">
      <p className="text-sm text-muted">Urgent referrals appear first in My work while they await handling.</p>
      {referral.urgency_changed_by && referral.urgency_changed_at ? <p className="text-sm">Last changed by {referral.urgency_changed_by.display_name} · {formatInstitutionalDateTime(referral.urgency_changed_at)}</p> : null}
      {canManage && !referral.voided_at ? <Button variant="secondary" disabled={pending || blocked || refreshFailed} onClick={() => void change()}>{pending ? "Saving…" : referral.is_urgent ? "Clear urgent flag" : "Mark urgent"}</Button> : null}
      {error ? <Notice role="alert" action={blocked ? <Button variant="secondary" disabled={pending} onClick={async () => { if (await refresh()) { setBlocked(false); setError(""); } }}>Refresh referral</Button> : undefined}>{error}</Notice> : null}
    </PanelBody>
    <ActionStatus status={status.status} onDismiss={status.dismiss} />
  </Panel>;
}
