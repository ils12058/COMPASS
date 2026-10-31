import type { Metadata } from "next";
import { FacultyReferralDetailPage } from "@/features/faculty-referrals/records";
export const metadata: Metadata = { title: "Referral details" };
export default async function Page({ params }: { params: Promise<{ referralId: string }> }) {
  const { referralId } = await params;
  return <FacultyReferralDetailPage referralId={referralId} />;
}
