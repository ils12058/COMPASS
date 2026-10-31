import type { Metadata } from "next";
import { FacultySubmitPage } from "@/features/faculty-referrals/submit-page";
export const metadata: Metadata = { title: "Submit Referral" };
export default function Page() { return <FacultySubmitPage />; }
