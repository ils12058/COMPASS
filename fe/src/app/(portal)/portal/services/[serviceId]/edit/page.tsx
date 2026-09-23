import { EditServicePage } from "@/features/services/service-editor-page";
import { ServicesManageGate } from "@/features/services/services-shared";

export default function Page() {
  return (
    <ServicesManageGate>
      <EditServicePage />
    </ServicesManageGate>
  );
}
