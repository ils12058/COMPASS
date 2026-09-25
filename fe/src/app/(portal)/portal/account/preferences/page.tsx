import type { Metadata } from "next";

import { PreferencesPage } from "@/features/account/preferences/preferences-page";

export const metadata: Metadata = { title: "Preferences" };

export default function Page() {
  return <PreferencesPage />;
}
