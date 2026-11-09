import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { FollowupsCreate } from "@/features/guidance-followups/followups-create";
export const metadata = { title: "Create Follow-Up" };
export default function Page() { return <div className={pageSheetWidth}><Suspense fallback={<p role="status">Loading Follow-Up form…</p>}><FollowupsCreate /></Suspense></div>; }
