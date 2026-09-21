# COMPASS Frontend

The COMPASS frontend is a Next.js application inside the main COMPASS monorepo. It consumes the backend-owned OpenAPI contract at `../contracts/openapi.json` and generates typed TanStack Query clients with Orval.

## Requirements

- Node.js 22.18 or newer
- pnpm 11.19.0

## Local development

Install dependencies and generate the API client:

```bash
cd fe
pnpm install
pnpm api:generate
```

For ordinary visual development against a local backend:

```env
COMPASS_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_TURNSTILE_SITE_KEY=
```

Then run:

```bash
pnpm dev
```

Browser code calls same-origin `/api/v1/...` routes. Next.js rewrites those requests to the server-only `COMPASS_API_BASE_URL`. The backend origin must not be exposed through a `NEXT_PUBLIC_*` variable.

## HTTPS auth development against staging

Live-staging authentication uses Secure cookies. To test the real auth flow through a local frontend, configure an uncommitted `.env.local`:

```env
COMPASS_API_BASE_URL=https://staging-api.compass-gco.com
NEXT_PUBLIC_TURNSTILE_SITE_KEY=<approved-staging-site-key>
```

Start the supported Next.js HTTPS development server:

```bash
pnpm dev:https
```

Use the HTTPS localhost address printed by Next.js. Do not put staging credentials, Turnstile secrets, MFA material, or auth cookies in local files that are committed.

### Staging CSRF requirement

The browser Origin for a local HTTPS frontend is an HTTPS localhost origin such as `https://localhost:3000`. The staging Django deployment must explicitly trust the exact development origin through `CSRF_TRUSTED_ORIGINS` for authenticated unsafe requests to succeed.

If Django returns `csrf_failed` because the localhost origin is not trusted, fix the staging deployment configuration. Do not strip or forge the Origin header, disable CSRF, or add permissive CORS.

### Staging Turnstile requirement

A Turnstile token created on localhost identifies the browser hostname used for the challenge. The staging Cloudflare site key and backend `TURNSTILE_EXPECTED_HOSTNAMES` must permit that hostname for full local-to-staging authentication testing.

If localhost is not approved, use an approved staging frontend hostname instead. Do not weaken Turnstile verification in application code.

## Authentication architecture

Django owns authentication policy and session validity. The browser uses backend-issued HttpOnly cookies and never stores an auth credential in localStorage, sessionStorage, or IndexedDB.

Unsafe API requests bootstrap a CSRF token from `GET /api/v1/auth/csrf`, keep the masked token in memory, and send it as `X-CSRFToken`. The frontend does not depend on the backend CSRF cookie name.

Turnstile tokens, passwords, MFA codes, TOTP provisioning data, recovery codes, and login challenges are transient and must not be persisted or logged.

The protected portal determines authentication through `GET /api/v1/auth/session`. The auth cookie is scoped to `/api/`, so page middleware must not attempt to inspect it.

## Validation

```bash
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
```

Or run the complete frontend gate:

```bash
pnpm validate
```

## API contract policy

- `contracts/openapi.json` is the single committed wire contract.
- Orval reads that root contract directly.
- Generated code lives under `src/lib/api/generated/` and is reproducible build output.
- Do not edit or commit generated client files.
- Do not create handwritten copies of generated DTOs.
- The shared Fetch transport uses cookie credentials and the same-origin API boundary.
- Authentication remains owned by Django. Do not add JWT or browser-storage authentication.

## Design-source policy

The legacy `reynantlntno/compass-fe@staging` repository is visual-reference material only. The new frontend selectively preserves COMPASS colors, spacing, radius, focus behavior, and typography. Legacy feature components, API wrappers, session behavior, large feature stylesheets, workflow assumptions, and copy are not migration sources.

## Styling

Use centralized design tokens, Tailwind utilities, and small reusable primitives. Keep feature-specific styles bounded to the feature that owns them; do not recreate a monolithic portal stylesheet.
