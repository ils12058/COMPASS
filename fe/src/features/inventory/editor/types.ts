import type { InventoryPayload, InventoryProgramSummary, ProgramSummary } from "@/lib/api/generated/model";

export type InventorySectionProps = {
  draft: InventoryPayload;
  onChange: (patch: Partial<InventoryPayload>) => void;
  programSnapshot?: InventoryProgramSummary | null;
  activePrograms?: ProgramSummary[];
  programLookupPending?: boolean;
  programLookupError?: boolean;
  programDiscoveryAllowed?: boolean;
};
