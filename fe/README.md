# COMPASS frontend

This directory contains the fresh COMPASS frontend foundation. Archived frontend
implementations are reference-only and are not an implementation authority.

## Prerequisites

- Node.js 22.18.0 or newer
- pnpm 11.19.0

## Local setup

```bash
pnpm install
cp .env.example .env.local
pnpm api:generate
pnpm dev
```

`COMPASS_API_BASE_URL` is server-only. When set, Next.js rewrites same-origin
browser requests under `/api/v1/` to the configured backend. Frontend code must
not call the backend origin directly.

## API contract and generation

The backend-owned contract at `../contracts/openapi.json` is the wire-contract
authority. Orval generates Fetch and TanStack Query integrations under
`src/lib/api/generated/`:

```bash
pnpm api:generate
```

Generated code is ignored by Git and must not be edited manually. Change the
OpenAPI contract, Orval configuration, or shared transport as appropriate.

## Institutional time

Frontend institutional chronology is owned by `src/lib/institutional-time.ts`. UCN wall-clock
inputs are interpreted as `Asia/Manila` (`Philippine Time`) regardless of the browser/device
timezone, institutional timestamp displays set an explicit timezone, and date-only contracts are
formatted without converting through browser-local midnight. `src/lib/date-time.ts` currently
keeps compatibility aliases for unmigrated feature callers; new code should use the explicit
institutional helper names directly.

## Commands

Frontend interaction and copy guidance: [UI information hierarchy](docs/ui-guidelines.md).
The [page-density audit](docs/ui-density-audit.md) records the ADR-091 consolidation and validation.

```bash
pnpm dev
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm validate
pnpm test:ui
```

`pnpm validate` regenerates the client, runs lint and strict type checking, and
creates a production build.

`pnpm test:ui` runs the synthetic browser regressions against a local Next server on
port 3107 (`pnpm dev --port 3107`); see the audit for browser setup and coverage. The
E-Counseling suites (`tests/ecounseling-call.browser.mjs` for the session page and
`tests/ecounseling-runtime.browser.mjs` for the call across portal pages) install a fake Daily Call
Object through a development-only seam, so they need the development server, never reach Daily,
and use synthetic camera and microphone tracks. Complete API generation before
running tests, since regeneration temporarily removes the generated client directory.
