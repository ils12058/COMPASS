import { Suspense } from "react";
import { CoveragePage } from "@/features/counseling/coverage/coverage-page";
export const metadata = {title:"Case coverage"};
export default function Page(){ return <Suspense fallback={<p role="status">Loading case coverage…</p>}><CoveragePage /></Suspense>; }
