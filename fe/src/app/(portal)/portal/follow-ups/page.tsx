import { Suspense } from "react";
import { FollowupsList, FollowupsListLoading } from "@/features/guidance-followups/followups-list";
export const metadata = { title: "Follow-Ups" };
export default function Page() { return <Suspense fallback={<FollowupsListLoading />}><FollowupsList /></Suspense>; }
