import { OrganizationStructureGate } from "@/features/organization/components/organization-gate";
import { OrganizationStructurePage } from "@/features/organization/structure/organization-structure-page";

export default function Page() {
  return (
    <OrganizationStructureGate>
      <OrganizationStructurePage />
    </OrganizationStructureGate>
  );
}
