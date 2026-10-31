import type { Metadata } from "next";
import { FacultyReferralsPage } from "@/features/faculty-referrals/records";
export const metadata: Metadata = { title: "My Referrals" };
export default function Page() { return <FacultyReferralsPage />; }
