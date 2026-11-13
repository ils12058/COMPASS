import { pageSheetWidth } from "@/components/ui/page-width";
import { Suspense } from "react";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";
import { FollowupsDetail } from "@/features/guidance-followups/followups-detail";
export const metadata = { title: "Follow-Up details" };
export default async function Page({ params }: { params: Promise<{ followupId: string }> }) { const { followupId } = await params; return <div className={pageSheetWidth}><Suspense fallback={<EncounterDetailSkeleton />}><FollowupsDetail id={followupId} /></Suspense></div>; }
