import type { Metadata } from "next";

export const metadata: Metadata = { title: "E-Counseling Session" };

import { ECounselingWorkspace } from "@/features/ecounseling/ecounseling-workspace";

export default async function Page({ params }: { params: Promise<{ appointmentId: string }> }) {
  const { appointmentId } = await params;
  // Keyed so another Appointment never inherits this one's call or session state.
  return <ECounselingWorkspace key={appointmentId} appointmentId={appointmentId} />;
}
