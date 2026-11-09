"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { fontVariables } from "@/styles/fonts";
import "@/styles/globals.css";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en" className={fontVariables}>
      <body>
        <title>Couldn&apos;t load COMPASS</title>
        <main className="mx-auto flex min-h-dvh max-w-2xl items-center px-6 py-12">
          <section>
            <h1 className="mt-6 font-heading text-3xl font-bold text-ink">
              Couldn&apos;t load COMPASS
            </h1>
            <p className="mt-3 leading-7 text-muted">
              Try again. If this keeps happening, contact the Guidance Office.
            </p>
            <Button className="mt-6" onClick={reset}>
              Try again
            </Button>
          </section>
        </main>
      </body>
    </html>
  );
}
