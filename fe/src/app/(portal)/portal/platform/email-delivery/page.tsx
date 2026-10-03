import type { Metadata } from "next";

export const metadata: Metadata = { title: "Email Delivery" };

import { PlatformEmailDeliveryPage } from "@/features/platform/email-delivery/platform-email-delivery-page";

export default function Page() {
  return <PlatformEmailDeliveryPage />;
}
