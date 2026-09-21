# COMPASS Frontend Architecture Rules

These rules apply to future work under `fe/`.

## Contract authority

The backend-owned `../contracts/openapi.json` is the wire contract. Generate client schemas, request functions, query keys, and hooks with Orval. Do not handwrite duplicate DTOs, enums, response parsers, or runtime validators that merely mirror generated contract types.

A UI-specific view model is appropriate only when it represents genuinely transformed presentation state.

## Server state

Use TanStack Query and Orval-generated query/mutation helpers for remote state. React state is for local interface state.

Do not rebuild per-feature server-state machinery from `useEffect`, `AbortController`, manual caches, focus listeners, loading flags, or custom refresh loops.

## HTTP and authentication

Browser API traffic stays on same-origin `/api/v1/...` paths. The shared transport owns cookie credentials, CSRF forwarding when a browser CSRF token already exists, response parsing, and structured HTTP errors.

Django remains authoritative for authentication and authorization. Never add bearer-token, JWT, localStorage, or sessionStorage authentication.

## Authorization

Frontend visibility is not security enforcement. Safe capability/context projections may hide unavailable actions, but access must never be inferred from role, College, Head designation, route visibility, or local frontend state.

## Components

Split feature code by responsibility: page composition, filters, lists, details, forms, mutations, and contextual panels. Do not place an entire operational module into one giant client component.

## Styling

Use `src/styles/tokens.css`, Tailwind utilities, and small bounded primitives. Do not introduce a giant global feature stylesheet.

## Copy

Write for the actual Student, Counselor, GCO Services Staff, Head Guidance Counselor, or IT Admin. Do not expose internal backend terms such as projection, resource scope, context grant, mutation, or governance lifecycle unless the user-facing workflow genuinely uses them.

## Legacy frontend

`reynantlntno/compass-fe@staging` is visual reference only. Preserve useful visual DNA; do not copy its feature architecture, API/session wrappers, navigation capability registry, DTO/parsing layers, giant stylesheets, workflow assumptions, or legacy page copy.
