import { Suspense } from "react";
import { WorkQueuePage, WorkQueueLoading } from "@/features/work-queue/work-queue-page";

export default function Page() {
  return <Suspense fallback={<WorkQueueLoading />}><WorkQueuePage /></Suspense>;
}
