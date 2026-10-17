import { pageSheetWidth } from "@/components/ui/page-width";
import { FollowupsDetail } from "@/features/guidance-followups/followups-detail";
export const metadata = { title: "Follow-Up Details" };
export default async function Page({ params }: { params: Promise<{ followupId: string }> }) { const { followupId } = await params; return <div className={pageSheetWidth}><FollowupsDetail id={followupId} /></div>; }
