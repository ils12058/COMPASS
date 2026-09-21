import type { Metadata } from "next";

import { ResourcesIndex } from "@/features/public/resources/resources-index";

export const metadata: Metadata = {
  title: "Resources",
};

export default function ResourcesPage() {
  return <ResourcesIndex />;
}
