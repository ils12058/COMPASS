"use client";

import Link from "next/link";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <head>
        <meta name="robots" content="noindex,nofollow" />
        <title>COMPASS — We hit a snag</title>
      </head>
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          background: "#f7f3ea",
          color: "#222a2d",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <main
          style={{
            minHeight: "100vh",
            display: "grid",
            placeItems: "center",
            padding: "2rem",
            boxSizing: "border-box",
          }}
        >
          <section
            style={{
              width: "min(100%, 34rem)",
              border: "1px solid #d8d7cb",
              borderRadius: "1rem",
              background: "#fffdf8",
              padding: "2rem",
              textAlign: "center",
            }}
          >
            <p style={{ fontWeight: 700, color: "#936515" }}>COMPASS</p>
            <h1 style={{ margin: "0.5rem 0", fontSize: "2rem" }}>
              We couldn’t open this page.
            </h1>
            <p style={{ lineHeight: 1.6, color: "#59636a" }}>
              Please try again, or go back to the COMPASS home page.
            </p>
            <div
              style={{
                marginTop: "1.5rem",
                display: "flex",
                justifyContent: "center",
                gap: "0.75rem",
                flexWrap: "wrap",
              }}
            >
              <button
                type="button"
                onClick={reset}
                style={{
                  minHeight: "2.75rem",
                  border: 0,
                  borderRadius: "0.5rem",
                  background: "#6b1f2a",
                  color: "#ffffff",
                  padding: "0.65rem 1rem",
                  font: "inherit",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Try again
              </button>
              <Link
                href="/"
                style={{
                  minHeight: "2.75rem",
                  display: "inline-flex",
                  alignItems: "center",
                  border: "1px solid #aeb3aa",
                  borderRadius: "0.5rem",
                  color: "#4d1520",
                  padding: "0.65rem 1rem",
                  fontWeight: 700,
                }}
              >
                Back to COMPASS
              </Link>
            </div>
          </section>
        </main>
      </body>
    </html>
  );
}
