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
        <title>COMPASS could not load</title>
        <main className="mx-auto flex min-h-dvh max-w-2xl items-center px-6 py-12">
          <section>
            <h1 className="font-heading text-3xl font-bold text-ink">
              COMPASS could not load
            </h1>
            <p className="mt-3 leading-7 text-muted">
              Try the request again. If the problem continues, contact COMPASS
              support.
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
