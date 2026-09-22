import type { Metadata } from "next";

import { ProfilePage } from "@/features/account/profile/profile-page";

export const metadata: Metadata = { title: "Profile | COMPASS" };

export default function Page() {
  return <ProfilePage />;
}
