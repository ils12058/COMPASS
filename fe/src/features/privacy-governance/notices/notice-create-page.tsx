"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  emptyNoticeRevisionValues,
  noticeFieldLabels,
  noticeRevisionCreateRequest,
  NoticeRevisionFields,
  type NoticeRevisionValues,
} from "@/features/privacy-governance/notices/notice-revision-fields";
import {
  ActionMessages,
  FieldHint,
  FormSection,
  PrivacyPageHeader,
  secondaryLinkClass,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  getPrivacyGovernanceListNoticesQueryKey,
  usePrivacyGovernanceCreateNotice,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

export function NoticeCreatePage() {
  const { canManage } = usePrivacyAccess();
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = usePrivacyGovernanceCreateNotice();
  const action = usePrivacyAction(noticeFieldLabels);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [revision, setRevision] = useState<NoticeRevisionValues>(emptyNoticeRevisionValues);
  const [audienceError, setAudienceError] = useState<string | null>(null);

  if (!canManage) {
    return (
      <WorkspaceUnavailable title="Privacy notice creation unavailable">
        Your current access does not include managing Privacy Governance records.
      </WorkspaceUnavailable>
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (revision.audiences.length === 0) {
      setAudienceError("Select at least one audience.");
      return;
    }
    setAudienceError(null);
    const result = await action.run(
      () =>
        create.mutateAsync({
          data: { code, name, ...noticeRevisionCreateRequest(revision) },
        }),
      "The privacy notice could not be created.",
    );
    if (!result) return;
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceListNoticesQueryKey(),
    });
    router.push(`/portal/privacy/notices/${result.data.id}?created=1`);
  }

  return (
    <section>
      <PrivacyPageHeader
        title="Create privacy notice"
        backHref="/portal/privacy/notices"
        backLabel="Privacy Notices"
        description="Creating a notice also creates revision 1 as a draft. People see a notice only after a revision is published."
      />
      <form className="max-w-3xl space-y-8" onSubmit={(event) => void submit(event)}>
        <FormSection title="Notice">
          <div className="grid gap-2">
            <Label htmlFor="notice-code">Internal code</Label>
            <FieldHint id="notice-code-hint">
              Use a stable internal code of letters, digits, dots, underscores, or
              hyphens. COMPASS stores it in uppercase. The code cannot be changed
              later.
            </FieldHint>
            <Input
              id="notice-code"
              required
              maxLength={64}
              autoComplete="off"
              spellCheck={false}
              className="max-w-sm font-mono"
              value={code}
              aria-describedby="notice-code-hint"
              onChange={(event) => setCode(event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="notice-name">Notice name</Label>
            <FieldHint id="notice-name-hint">
              Identifies this notice in COMPASS. Each revision has its own title.
            </FieldHint>
            <Input
              id="notice-name"
              required
              maxLength={160}
              value={name}
              aria-describedby="notice-name-hint"
              onChange={(event) => setName(event.target.value)}
            />
          </div>
        </FormSection>

        <FormSection title="Revision 1">
          <NoticeRevisionFields
            idPrefix="notice-revision"
            values={revision}
            audienceError={audienceError}
            onChange={(next) => {
              setRevision(next);
              if (next.audiences.length > 0) setAudienceError(null);
            }}
          />
        </FormSection>

        <ActionMessages error={action.error} notice={action.notice} />

        <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-6">
          <Link href="/portal/privacy/notices" className={secondaryLinkClass}>
            Cancel
          </Link>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create privacy notice"}
          </Button>
        </div>
      </form>
      {action.stepUpDialog}
    </section>
  );
}
