import { OrganizationManageGate } from "@/features/organization/components/organization-gate";
import { ResponsibilitiesPage } from "@/features/organization/responsibilities/responsibilities-page";

export default function Page() {
  return (
    <OrganizationManageGate>
      <ResponsibilitiesPage />
    </OrganizationManageGate>
  );
}
