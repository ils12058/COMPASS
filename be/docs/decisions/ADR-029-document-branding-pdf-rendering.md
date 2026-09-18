# ADR-029: Institutional Document Branding and PDF Rendering Foundation

## Context

COMPASS needs a shared foundation for institution-branded printable documents without coupling
branding presentation to Referral, Call Slip, Good Moral, reports, or other business domains.

The current repository has Django app templates enabled through `APP_DIRS=True`, while ordinary
`staticfiles` storage is S3-compatible remote storage. That ordinary static URL path is unsuitable
for deterministic server-side PDF rendering because a render would then depend on MinIO/S3 or
network availability.

The currently supplied standalone UCN logo, Bagong Pilipinas logo, and accreditation/recognition
footer strip are explicitly approved for immediate COMPASS use. They are interim production assets
and are intentionally replaceable later. The supplied sample institutional document is a visual
reference only; COMPASS does not crop logos or other assets from that screenshot.

## Decision

### Documents owns presentation infrastructure

Create a focused `compass.documents` domain for branding facts, packaged document assets, shared
print CSS, code-owned layout primitives/template registry, trusted Django-template rendering, and
local Chromium HTML-to-PDF rendering.

Institutional Forms remains the owner of controlled QMS FormFamily/FormRevision identity.
Documents does not add presentation semantics to `FormRevision`.

No Referral, Call Slip, Good Moral, report, or other business-specific PDF endpoint is introduced by
this foundation.

### Branding profile is a narrow singleton configuration

`DocumentBrandingProfile` uses a UUID primary key and the unique supported key `default`.
A database check constraint rejects any other key. The forward migration bootstraps exactly one
profile.

Only confirmed institutional facts are seeded:

- `Republic of the Philippines`
- `University of Camarines Norte`
- `UCN`
- `Camarines Norte State College`
- `Guidance and Counseling Office`

The visual reference's College of Education, GTAO, email/address, and other office-specific facts are
not inferred into the GCO profile. Unknown contact/unit fields start as NULL.

Required institutional identity fields cannot become blank. Optional strings normalize blank or
whitespace to NULL. Email and URL fields use Django field validation.

There is no profile create/delete/list-all API.

### Head Guidance configuration authority

Capabilities `document_branding.view` and `document_branding.manage` are granted only by the
`HEAD_GUIDANCE_COUNSELOR` designation. They are not Counselor-role grants and are not granted to IT
Admin, GSS, Student, or DPO.

The API is:

- `GET /api/v1/document-branding/profile` — `documentBrandingGetProfile`
- `PATCH /api/v1/document-branding/profile` — `documentBrandingUpdateProfile`

Mutation additionally requires the repository's existing recent-MFA mechanism through
`require_recent_mfa(request.auth_session)`.

Successful material changes append `document_branding.updated` in the same transaction. Audit
target type is `documents.documentbrandingprofile`. Metadata contains only the profile key and
sorted changed-field names. Branding values, emails, URLs, addresses, phone numbers, rendered HTML,
and request payloads are not copied to Audit. A no-op PATCH does not append a new Audit event.

### Approved assets are packaged local resources

The currently approved supplied standalone assets are committed under stable code-owned names:

- `documents/branding/ucn-logo.png`
- `documents/branding/bagong-pilipinas.png`
- `documents/branding/footer.png`

They may later be replaced by better-quality/final files without a database migration or changes to
Referral, Call Slip, or other business records, provided the stable asset contract remains intact.

The footer remains one flattened recognition/accreditation strip in this foundation. COMPASS does
not model each logo or award as database configuration.

Document rendering deliberately does not use Django's public/static S3 URL. Asset bytes are resolved
from packaged `compass.documents` resources and embedded as `data:` URIs. Shared print CSS is also
read locally and inlined into trusted HTML. This keeps rendering independent from S3/static HTTP
availability.

### Code-owned layouts and template registry

The foundation provides four reusable layout families: `STANDARD_LETTERHEAD`, `COMPACT_FORM`,
`CERTIFICATE`, and `REPORT`.

A frozen `DocumentTemplateSpec` registry maps a known key/version to a fixed Django template,
layout family, and narrow page options.

There is no registration API, database table, plugin loader, caller-controlled template path, or
dynamic import. Unknown key/version pairs fail closed.

The foundation includes only test/foundation fixture templates. It does not fabricate business
documents merely to exercise the layouts.

Presentation template version is distinct from QMS FormRevision identity.

### Controlled-form metadata is explicit historical context

The shared controlled-form metadata partial renders only metadata supplied explicitly by the caller,
such as historical official code/revision and source page label.

A future business-domain renderer must pass the `FormRevision` already referenced by the
historical domain record. It must not query today's active FormRevision while re-rendering an older
Referral, Call Slip, certificate, or report.

### Trusted Django HTML rendering

The renderer accepts only a code-owned template key/version and a context dictionary. Reserved
foundation values override same-named caller context: branding profile, packaged assets, inline print
CSS, and template spec/layout family.

Django autoescaping remains enabled for variable content.

The renderer does not accept arbitrary HTML as the primary document contract and never accepts a
caller-provided template path.

### Local Chromium PDF rendering

Playwright Python 1.63.0 is a normal runtime dependency because PDF generation is application
functionality, not pytest tooling.

PDF rendering uses the synchronous Playwright API and Chromium headless mode:

1. render trusted Django HTML locally
2. launch Chromium
3. create a context with JavaScript disabled and service workers blocked
4. create a page and register a route guard
5. load the trusted HTML with `page.set_content(...)`
6. fail if any HTTP/HTTPS resource is attempted
7. generate A4 PDF bytes with print backgrounds and CSS page-size preference

The renderer never calls `page.goto(user_input)`.

Unexpected HTTP/HTTPS requests are aborted and make the render fail rather than silently emitting an
incomplete PDF.

PDF output is validated to begin with `%PDF-` and to contain a nontrivial payload.

Shared CSS owns A4 `@page` sizing and print-safe table/page-break rules.

Optional browser Page X of Y output uses a code-owned Playwright footer template. Header/footer
templates carry their own trusted inline styling because Playwright page header/footer content does
not inherit document CSS.

### Timeout semantics

`DOCUMENT_RENDER_TIMEOUT_SECONDS` controls browser launch and HTML-content operation timeouts and
must be between 1 and 120 seconds.

Playwright's `page.pdf()` does not expose a direct per-call timeout. This foundation therefore does
not claim that the setting provides a hard wall-clock kill around PDF generation itself.

If future production evidence requires a strict hard render deadline, COMPASS should introduce a
separate process/worker boundary that can be terminated safely rather than pretending asyncio task
cancellation is a supported Chromium kill mechanism.

### Browser deployment

The backend image remains based on Python 3.13 slim Bookworm.

The browser is installed into a shared path `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`.

The container installs only Chromium's headless shell and required Linux dependencies using
`uv run playwright install --with-deps --only-shell chromium`. The installed browser tree is made
readable/executable by the non-root `compass` application user.

COMPASS does not add an explicit `--no-sandbox` browser flag. This ADR also does not make a stronger
claim that Chromium sandboxing is fully enabled merely because the application process runs as a
non-root user; production container hardening may later add user-namespace/seccomp configuration for
stronger Chromium sandbox isolation.

### No persistence or delivery side effects

This foundation returns PDF bytes through a small immutable render result.

It introduces no GeneratedDocument model, PDF/object-storage write, retention/archive/delete policy,
email or notification delivery, Celery document task, outbox intent, Referral/Call Slip/Good Moral
PDF endpoint, or arbitrary uploadable document template.

Future document-generation slices can deliberately decide when rendered bytes are downloaded,
stored, emailed, or otherwise distributed.

### Validation

Targeted validation retains every existing regression suite and adds `tests/test_documents.py`.

The focused suite covers exact bootstrap identity and unknown NULL fields, singleton key
enforcement, branding validation/normalization, Head-only capabilities and recent MFA, privacy-safe
Audit metadata, approved local asset/data-URI resolution, Django autoescaping, code-owned template
lookup and unknown-template rejection, optional accreditation footer behavior, explicit historical
controlled-form metadata, absence of generated-document persistence, a real Chromium PDF smoke,
rejection of attempted remote rendering resources, controlled browser unavailable/timeout failures,
and absence of URL navigation in the renderer.

CI installs the locked Python dependencies, installs only Chromium headless shell with dependencies,
runs the normal static/migration/OpenAPI checks, then runs the existing targeted matrix plus the
document suite.

The full backend suite remains unnecessary by default.

## Consequences

COMPASS gains a reusable institution-branded PDF rendering substrate without coupling presentation
to business records or remote static storage.

The currently supplied standalone images are useful immediately but remain replaceable later.
Branding facts can be maintained by Head Guidance through a narrowly authorized recent-MFA-protected
configuration path. QMS document identity remains historical domain truth rather than presentation
configuration.

Actual business-document generation remains future work built on this foundation.
