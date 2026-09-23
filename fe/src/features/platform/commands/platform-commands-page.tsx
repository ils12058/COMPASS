"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  PlatformPageHeader,
  PlatformQueryError,
  PlatformRowsSkeleton,
} from "@/features/platform/platform-presentation";
import { usePlatformOperationsCommandCatalog } from "@/lib/api/generated/platform-operations/platform-operations";

const categoryLabels: Record<string, string> = {
  BOOTSTRAP: "Bootstrap",
  DEPLOYMENT: "Deployment",
  DIAGNOSTIC: "Diagnostic",
};

export function PlatformCommandsPage() {
  const catalog = usePlatformOperationsCommandCatalog({
    query: { retry: false, staleTime: 60_000 },
  });
  const result = catalog.data?.data;
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);

  async function copyCommand(code: string, invocation: string) {
    setCopyError(null);
    setCopiedCode(null);
    try {
      await navigator.clipboard.writeText(invocation);
      setCopiedCode(code);
    } catch {
      setCopyError("The command could not be copied. Select and copy its text instead.");
    }
  }

  return (
    <section>
      <PlatformPageHeader
        title="Operator commands"
        description="Read-only command reference. Commands cannot be executed from the browser."
      />

      {catalog.isPending ? <PlatformRowsSkeleton rows={4} /> : null}
      {catalog.isError && !result ? (
        <PlatformQueryError
          message="The operator command catalog could not be loaded."
          onRetry={() => void catalog.refetch()}
        />
      ) : null}

      {result ? (
        <>
          {result.execution_supported ? (
            <p className="mb-5 border-l-2 border-warning pl-4 text-sm leading-6 text-muted">
              The catalog advertises execution support, but this workspace remains reference-only.
            </p>
          ) : (
            <p className="mb-5 border-l-2 border-info pl-4 text-sm leading-6 text-muted">
              Execution is not supported. Use the documented operator process outside the browser.
            </p>
          )}

          {copyError ? (
            <p role="alert" className="mb-4 text-sm text-danger">
              {copyError}
            </p>
          ) : null}
          {copiedCode ? (
            <p role="status" className="mb-4 text-sm text-success">
              Command copied.
            </p>
          ) : null}

          {result.commands.length ? (
            <ol className="divide-y divide-border border-y border-border">
              {result.commands.map((command) => (
                <li key={command.code} className="py-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-muted">
                        {categoryLabels[command.category] ??
                          command.category.replaceAll("_", " ").toLowerCase()}
                      </p>
                      <h2 className="mt-1 font-heading text-lg font-semibold text-ink">
                        {command.display_name}
                      </h2>
                      <p className="mt-1 text-sm leading-6 text-ink">
                        {command.purpose}
                      </p>
                    </div>
                    <Button
                      variant="secondary"
                      aria-label={`Copy command: ${command.display_name}`}
                      onClick={() =>
                        void copyCommand(command.code, command.invocation)
                      }
                    >
                      {copiedCode === command.code ? "Copied" : "Copy command"}
                    </Button>
                  </div>
                  <pre className="mt-4 overflow-x-auto whitespace-pre-wrap break-all rounded-md border border-border bg-surface-muted p-3 text-xs leading-5 text-ink">
                    <code>{command.invocation}</code>
                  </pre>
                  <p className="mt-3 text-xs font-medium text-muted">
                    {command.mutates_state
                      ? "Changes system state"
                      : "Read-only"}
                  </p>
                  {command.notes ? (
                    <p className="mt-2 break-words text-sm leading-6 text-muted">
                      {command.notes}
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : (
            <p className="border-y border-border py-6 text-sm text-muted">
              No operator commands are available.
            </p>
          )}
        </>
      ) : null}
    </section>
  );
}
