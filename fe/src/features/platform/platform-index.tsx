"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function PlatformIndex() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/portal/platform/health");
  }, [router]);

  return (
    <p role="status" className="text-sm text-muted">
      Opening Platform health…
    </p>
  );
}
