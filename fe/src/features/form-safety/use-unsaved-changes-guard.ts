"use client";

import { useEffect, useId } from "react";
import { usePathname } from "next/navigation";

import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";

export function useUnsavedChangesGuard({
  dirty,
  message,
}: {
  dirty: boolean;
  message: string;
}) {
  const id = useId();
  const pathname = usePathname();
  const { registerGuard, unregisterGuard } = useUnsavedNavigation();

  useEffect(() => {
    if (!dirty) {
      unregisterGuard(id);
      return;
    }

    registerGuard(id, { message, pathname });
    return () => unregisterGuard(id);
  }, [
    dirty,
    id,
    message,
    pathname,
    registerGuard,
    unregisterGuard,
  ]);
}
