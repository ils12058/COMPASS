import { pageSheetWidth } from "@/components/ui/page-width";
import { FollowupsReport } from "@/features/guidance-followups/followups-report";
export const metadata = { title: "Follow-Up Report" };
export default function Page() { return <div className={pageSheetWidth}><FollowupsReport /></div>; }
