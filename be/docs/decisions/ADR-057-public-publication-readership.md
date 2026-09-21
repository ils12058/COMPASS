# ADR-057: Public Publication Readership

- **Status:** Accepted
- **Date:** 2026-09-21

## Context

ADR-053 established Announcements and Curated Resources as small publishing domains whose initial
readership required an active authenticated COMPASS account. The public-facing Guidance and
Counseling Office site now needs a deliberately public subset of those publications without
weakening the authenticated audience model or private Resource storage.

## Decision

The shared `PublicationAudience` vocabulary gains one explicit `PUBLIC` value. `PUBLIC` means a
published item may be read anonymously and by authenticated users. `ALL_AUTHENTICATED` keeps its
existing meaning: any active authenticated COMPASS account. Student and GCO-personnel audiences
remain authenticated role-eligible audiences.

Authenticated audience eligibility includes `PUBLIC` plus `ALL_AUTHENTICATED` and any existing
role-specific audience. Anonymous access does not fabricate a User and does not call the
actor-based reader services. Announcements and Resources instead expose narrow public read
services that require `audience=PUBLIC`, `status=PUBLISHED`, and a reached `published_at`.
Announcement expiry continues to apply to anonymous readers.

The API adds anonymous GET-only routes under `/api/v1/public/announcements` and
`/api/v1/public/resources`. Existing authenticated reader and management routes remain
authenticated and keep their operation IDs.

FILE Resources continue to use private object storage. A visible PUBLIC, PUBLISHED FILE may request
a short-lived signed URL after the backend public-visibility check. Raw storage keys and permanent
object URLs are never public API fields, and no storage bucket or object is made public.

This extension is not a generic public CMS. It does not add comments, reactions, read receipts,
analytics, scheduled publishing, tags, folders, custom audience lists, or College-specific public
targeting. Publishing also continues not to send Notifications or email automatically.

## Consequences

- The UCN Guidance and Counseling Office can publish a small anonymous-readable subset without
  redefining authenticated audiences.
- Authenticated users also receive PUBLIC publications through the existing visibility model.
- Non-public, draft, archived, future, and expired content stays hidden from anonymous callers.
- Private file storage remains provider-neutral and private while supporting controlled public
  downloads through expiring signed URLs.
- ADR-053 remains the foundation decision; this ADR extends only its readership model.
