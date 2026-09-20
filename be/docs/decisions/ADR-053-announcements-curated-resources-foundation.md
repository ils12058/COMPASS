# ADR-053: Announcements and Curated Resources Foundation

- **Status:** Accepted
- **Date:** 2026-09-20

## Context

COMPASS needs a small Guidance and Counseling Office publishing surface for time-sensitive office
Announcements and persistent curated Guidance Resources. These objects are informational
publications, not counseling records, Notifications, controlled institutional forms, or a generic
content-management system.

## Decision

Announcements and Resources are separate domain models and applications. Both use only the small
shared publication status and audience vocabulary; no generic content base model or publishing
framework is introduced.

Raw Markdown is the canonical content source. The backend does not render or store HTML.
Frontend consumers must treat body_markdown as untrusted source, keep raw embedded HTML
disabled or escaped, sanitize rendered output, and prevent unsafe URL schemes from executing.
Clients must not insert the source directly into innerHTML.

The initial audience classes are ALL_AUTHENTICATED, STUDENTS, and GCO_PERSONNEL.
Readership requires an active authenticated account, a currently visible PUBLISHED object, and
audience eligibility. Management capability does not change ordinary reader audience membership.

announcements.manage and resources.manage are baseline grants for COUNSELOR and
GUIDANCE_SERVICES_STAFF. A Head Guidance Counselor continues to receive the Counselor baseline
through the existing compatible role architecture. Publication is direct; no mandatory Head
approval workflow is added. Publication authority is GCO-wide and is not College-scoped.

Announcements follow DRAFT -> PUBLISHED -> ARCHIVED or DRAFT -> ARCHIVED. Publication is
immediate and optional expiry is enforced as a visibility rule; no scheduler is added. Initial
publication metadata is retained across published text corrections.

Resources follow the same terminal lifecycle and support exactly ARTICLE, EXTERNAL_LINK, and
FILE. Categories are a fixed small enum rather than a managed taxonomy. FILE Resources accept
one PDF up to 10 MiB while DRAFT. The application generates the private object key and stores only
structural file metadata. Published FILE replacement requires archiving the old Resource and
publishing a new one.

Resource files reuse the existing provider-neutral ObjectStorage boundary and private
S3-compatible storage. Reader authorization and Resource visibility are checked before a
short-lived signed storage URL is issued. Raw storage keys are not part of reader or management API
responses, and no bucket/object is made public.

Create, update, publish, archive, and meaningful file-attachment mutations are synchronously
audited with structural metadata only. Markdown bodies, file bytes, storage signatures, and
external URL query data are excluded from audit metadata.

Publishing an Announcement or Resource does not create an in-app Notification or email. No
read receipts, engagement analytics, comments, reactions, tags, folders, multiple attachments,
approval engine, public knowledge base, scheduled publication, or generic CMS features are part of
this foundation.

## Consequences

- The domain remains small enough to explain and audit during defense.
- Authenticated users see only audience-eligible currently published content.
- Authorized Counselors and Guidance Services Staff can publish without a Head approval bottleneck.
- FILE Resource history remains unambiguous because published file replacement is not in-place.
- A later requirement for College targeting, scheduled publication, publish-and-notify, or richer
  content workflows requires a separately reviewed enhancement.
