# COMPASS Frontend

The COMPASS frontend is a Next.js application inside the main COMPASS monorepo. It consumes the backend-owned OpenAPI contract at `../contracts/openapi.json` and generates typed TanStack Query clients with Orval.

## Requirements

- Node.js 22.18 or newer
- pnpm 11.19.0

## Local development

```bash
cd fe
pnpm install
pnpm api:generate
pnpm dev
```

Set the server-only API origin in a local environment file:

```bash
COMPASS_API_BASE_URL=http://127.0.0.1:8000
```

Browser code calls same-origin `/api/v1/...` routes. Next.js rewrites those requests to `COMPASS_API_BASE_URL`. Do not expose the backend origin through a `NEXT_PUBLIC_*` variable.

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
- Do not edit generated files or create handwritten copies of generated DTOs.
- The shared Fetch transport uses cookie credentials and the same-origin API boundary.
- Authentication remains owned by Django. Do not add JWT or browser-storage authentication.

## Design-source policy

The legacy `reynantlntno/compass-fe@staging` repository is visual-reference material only. The new frontend selectively preserves COMPASS colors, spacing, radius, focus behavior, and typography. Legacy feature components, API wrappers, session behavior, large feature stylesheets, workflow assumptions, and copy are not migration sources.

## Styling

Use centralized design tokens, Tailwind utilities, and small reusable primitives. Keep feature-specific styles bounded to the feature that owns them; do not recreate a monolithic portal stylesheet.
