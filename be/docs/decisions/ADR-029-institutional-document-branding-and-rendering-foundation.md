# ADR-029: Institutional Document Branding and PDF Rendering Foundation

## Context

COMPASS needs a shared foundation for future institutional outputs such as controlled forms,
certificates, formal office documents, and aggregate reports. The repository previously had no
shared document-branding configuration, HTML/PDF renderer, generated-document model, or
presentation-template system.

A current University of Camarines Norte document sample establishes visual direction such as the
UCN masthead, Bagong Pilipinas mark, maroon separator, office heading, and an optional
accreditation/recognition strip. The supplied sample belongs to another office (College of
Education / Guidance, Testing and Admission Office), so those office-specific facts are not
COMPASS Guidance and Counseling Office data.

The user separately supplied standalone UCN, Bagong Pilipinas, and accreditation/footer image
assets and explicitly approved them for immediate COMPASS use, with the understanding that they
may be replaced later by higher-quality/final versions. The sample screenshot remains visual
reference only and is never cropped for production assets.

## Decision

### One focused documents domain

Create `compass.documents` to own the shared institutional document foundation:

- one narrow `DocumentBrandingProfile`
- branding-profile service/API
- code-owned Django HTML templates and print CSS
- packaged branding assets
- a small code-owned template specification registry
- a local Playwright/Chromium HTML-to-PDF renderer

No business domain is modified merely to gain PDF capability.

### One current branding profile

`DocumentBrandingProfile` has UUID identity and the only supported key `default`.
A unique key plus database check constraint enforces the current single-profile design.

The bootstrap migration records only confirmed facts:

- Republic of the Philippines
- University of Camarines Norte
- UCN
- former institution name Camarines Norte State College
- Guidance and Counseling Office

Unknown address, contact, social, parent-unit, office-email, office-phone, and office-location facts
start as NULL. No College of Education, Guidance Testing and Admission Office, or
`coedgtao@ucn.edu.ph` data is copied from the visual sample.

Required identity fields reject blank/whitespace. Optional text is normalized so blank/whitespace
means NULL. Email and URL values use Django field validation only; COMPASS does not externally
verify or fetch submitted values.

### Head-only configuration authority

Capabilities are:

- `document_branding.view`
- `document_branding.manage`

They are granted only by the `HEAD_GUIDANCE_COUNSELOR` designation. They are not role grants for
ordinary Counselor, Guidance Services Staff, Student, IT Admin, or DPO.

The management API exposes only:

- `GET /api/v1/document-branding/profile`
- `PATCH /api/v1/document-branding/profile`

There is no create, delete, list-all, renderer, or arbitrary-template API. Profile mutation requires
the existing recent-MFA session mechanism.

Successful mutations append `document_branding.updated` synchronously in the same database
transaction as the update. Audit target type is `documents.documentbrandingprofile`; metadata is
restricted to the stable profile key and sorted changed-field names. Field values are never copied
into Audit metadata.

### Data and presentation remain separate

PostgreSQL owns institution and office facts only. HTML, CSS, image placement, page layout, and
template selection remain source-controlled code.

COMPASS does not introduce database-managed HTML/CSS, a WYSIWYG editor, a dynamic template
uploader, generic CMS blocks, or a form-design system.

Institutional branding is also separate from QMS controlled-form identity. Existing
`FormFamily`/`FormRevision` records continue to own official form codes, official revisions, and
internal schema versions. A historical code such as `CNSC-OP-GTA-01F8` remains historical truth
even when the masthead says University of Camarines Norte.

Controlled-form template partials accept explicit historical form metadata supplied by a future
domain renderer. They do not query the currently active FormRevision when re-rendering a historical
domain record.

### Code-owned layout families and template versions

The foundation defines four narrow presentation families:

- `STANDARD_LETTERHEAD`
- `COMPACT_FORM`
- `CERTIFICATE`
- `REPORT`

A frozen `DocumentTemplateSpec` registry binds an approved template key/version to a fixed Django
template path, layout family, and narrow page options. Caller-controlled template paths are not
supported.

COMPASS presentation-template version is not a QMS FormRevision. A CSS/layout change does not
automatically create a new institutional FormRevision, and a new QMS FormRevision may require a
future explicit template implementation.

This foundation includes only a test fixture to exercise the shared primitives; it does not create
actual Referral, Call Slip, Good Moral, Exit Interview, or Profiling Report PDFs.

### Supplied packaged assets

The currently supplied standalone files are packaged at stable code-owned paths:

- `documents/branding/ucn-logo.png`
- `documents/branding/bagong-pilipinas.png`
- `documents/branding/footer.png`

They are approved for present use and intentionally replaceable later without schema or
business-domain changes. They are not extracted from the screenshot.

The accreditation/footer strip is code-selected by the layout/template specification. It is not
represented as one database flag per logo.

No downloaded font binaries are added; print CSS uses ordinary system-safe font stacks.

### Local asset strategy

Normal COMPASS static storage is S3-compatible. Institutional rendering therefore does not use
public/static-storage URLs to draw its own packaged branding. The documents app resolves its
code-owned CSS and images from the installed Python package, embeds CSS directly, and converts image
bytes to `data:` URIs.

This avoids MinIO/S3/network availability becoming a prerequisite for rendering the institution's
own header.

### Playwright / Chromium rendering

The renderer uses Playwright Python 1.63.0 and Chromium. The internal pipeline is:

domain/test context
+ DocumentBrandingProfile
+ code-owned template spec
-> Django template rendering
-> trusted local CSS + packaged data-URI assets
-> Chromium
-> PDF bytes

The renderer uses `page.set_content()`, never caller-provided `page.goto()`. Django autoescaping
remains enabled for variable content. JavaScript is disabled and service workers are blocked.
Unexpected HTTP/HTTPS resource requests are aborted and cause the render to fail rather than
silently produce a partially network-dependent document.

PDF output uses print backgrounds and CSS-owned A4 page sizing. Optional browser page numbering is
presentation-only and remains separate from controlled-form code/revision metadata.

### Timeout semantics

`DOCUMENT_RENDER_TIMEOUT_SECONDS` bounds supported Playwright operations such as Chromium startup
and HTML/content loading. Playwright's current `page.pdf()` API has no direct timeout argument, so
this setting is not represented as a hard wall-clock kill around PDF generation.

Playwright timeout/unavailable failures are translated to controlled document-rendering exceptions.
A future process/worker boundary may provide a true hard kill if operational evidence requires it;
no browser pool, microservice, cluster, or retry framework is introduced here.

### Runtime and sandbox decision

The backend remains based on `python:3.13-slim-bookworm`. The image installs the Playwright
Chromium headless shell and required OS dependencies into a shared
`PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`, readable/executable after switching to the existing
non-root `compass` application user.

COMPASS does not add a custom `--no-sandbox` browser argument. This foundation also does not claim
that non-root execution alone enables Chromium's stronger user-namespace sandbox: Playwright's
default Chromium launch behavior remains in effect. Further sandbox hardening can be evaluated
separately if deployment policy requires user-namespace/seccomp configuration.

### CI

Targeted GitHub Actions remains the authoritative validation path. It installs only Playwright
Chromium (not Firefox/WebKit) and runs a real-browser PDF smoke test. The smoke verifies a
nontrivial `%PDF-` payload from deterministic local HTML/assets. Focused tests also verify that
unexpected remote resources are blocked.

The existing targeted regression matrix remains intact. The full backend suite is not required by
this foundation.

### No generated-document persistence yet

The renderer returns PDF bytes and template key/version metadata only. This foundation creates no:

- GeneratedDocument/RenderedPDF/DocumentArchive database model
- MinIO/S3 PDF persistence
- Referral or Call Slip PDF endpoint
- Good Moral workflow or certificate endpoint
- Profiling Report aggregation/output
- email template/sending
- notification model, outbox, reminder, or Celery delivery task
- digital signature, QR verification, or certificate-verification service

Future domain slices must decide whether issued artifacts should be streamed, cached, or persisted,
including any historical provenance requirements.

## Consequences

Future document-producing domains can share one institution/GCO identity source and one
network-isolated print pipeline without embedding presentation logic into Referral, Call Slip,
Counseling, Inventory, or other business models.

Branding facts may change for future renders through the Head-authorized profile API. Code-owned
presentation and replaceable packaged assets remain reviewable in version control. Historical QMS
identity remains independently governed by each domain record's FormRevision.

The current supplied raster assets are sufficient for immediate foundation use and may be swapped
later behind the same stable asset keys/paths.
