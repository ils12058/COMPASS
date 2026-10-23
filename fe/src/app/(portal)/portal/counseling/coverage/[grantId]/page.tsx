import { CoverageDetail } from "@/features/counseling/coverage/coverage-detail";
export const metadata = {title:"Coverage details"};
export default async function Page({params}: {params:Promise<{grantId:string}>}){const {grantId}=await params;return <CoverageDetail grantId={grantId} />;}
