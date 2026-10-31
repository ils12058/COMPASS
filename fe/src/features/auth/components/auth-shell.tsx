import type { ReactNode } from "react";

import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import styles from "./auth-shell.module.css";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-dvh flex-col bg-body">
      <div className={styles.campus} aria-hidden="true" />
      <header className="relative flex justify-end px-[min(1rem,4vw)] pt-2">
        <AccessibilityControl placement="header" />
      </header>
      <main className="relative flex flex-1 items-center px-[min(1rem,4vw)] pb-10 pt-2 sm:px-6 sm:pb-10">
        {children}
      </main>
    </div>
  );
}
