import type { ReactNode } from "react";

import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import styles from "./auth-shell.module.css";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-dvh overflow-x-clip bg-body">
      <div className={styles.campus} aria-hidden="true" />
      <main className="relative flex min-h-dvh items-center px-4 pb-24 pt-10 sm:px-6 sm:py-10">
        {children}
      </main>

      <AccessibilityControl placement="floating" />
    </div>
  );
}
