import { ECounselingWorkspace } from "@/features/ecounseling/ecounseling-workspace";

export default async function Page({ params }: { params: Promise<{ appointmentId: string }> }) {
  const { appointmentId } = await params;
  return <ECounselingWorkspace appointmentId={appointmentId} />;
}
