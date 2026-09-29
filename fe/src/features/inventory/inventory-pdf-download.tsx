"use client";

import { useState } from "react";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { inventoryErrorMessage } from "@/features/inventory/inventory-shared";
import { inventoryDownloadMyPdf, inventoryDownloadRecordPdf } from "@/lib/api/generated/inventory/inventory";
import { downloadBinaryResponse } from "@/lib/browser-download";

export function InventoryPdfDownload({
  inventoryId,
  studentFacing,
}: {
  inventoryId: string;
  studentFacing: boolean;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setPending(true);
    setError(null);
    try {
      const response = studentFacing
        ? await inventoryDownloadMyPdf(inventoryId)
        : await inventoryDownloadRecordPdf(inventoryId);
      downloadBinaryResponse(response, `individual-inventory-${inventoryId}.pdf`);
    } catch (caught) {
      setError(inventoryErrorMessage(caught, "The official Individual Inventory PDF could not be released right now. Try again later."));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <Button variant="secondary" onClick={() => void download()} disabled={pending}>
        <Download aria-hidden="true" size={16} />
        {pending ? "Preparing official PDF…" : "Download official PDF"}
      </Button>
      {error ? <p role="alert" className="max-w-lg text-sm text-danger">{error}</p> : null}
    </div>
  );
}
