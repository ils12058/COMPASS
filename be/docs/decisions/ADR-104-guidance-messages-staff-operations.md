# ADR-104: Guidance Messages staff operations and templates

## Status

Accepted. Refines [ADR-102](ADR-102-guidance-messages-backend-foundation.md) (Office handler
assignment) and reuses the shared conversation pieces of
[ADR-103](ADR-103-contextual-guidance-messages.md). Neither is rewritten.

## Context

ADR-102 gave Office threads an `assigned_to` handler and a `PATCH .../handler` mutation, but no
safe way for the frontend to know who may be assigned, so reassignment stayed hidden. Guidance staff
also retype the same generic replies many times a day. Both are staff productivity gaps inside the
existing Messages domain; neither needs a workflow engine or another messaging system.

## Decision

### Office handler assignment

**Assignment is workflow ownership, never authorization.** `GuidanceThread.assigned_to` says who
follows up. Content access still comes only from current canonical workload (ADR-099): an assignee
who loses that workload loses the thread even while still named as its handler, and staff who are
not the assignee keep the thread while their workload covers it.

**A thread-scoped eligible-handler list.**
`GET /api/v1/guidance-messages/threads/{thread_id}/eligible-handlers`
(`guidanceMessagesListEligibleHandlers`) returns `{items: [{id, display_name, role}], page,
page_size, has_next}`. The role is only `COUNSELOR` or `GUIDANCE_SERVICES_STAFF`; there is no email,
account state, capability, designation, supervision or College data. It is `no-store, private`.

* Only for an Office thread the requester can manage now (active staff with
  `guidance_messages.manage` whose workload covers its routing College). Anything else, including a
  Counseling thread, a guessed ID or a view-only actor, is the ordinary concealed 404.
* Candidates are a finite superset (the College's explicit Counselor, every Head for the unique-Head
  fallback, and the staff they supervise), each then checked with the same `require_thread(...,
  manage=True, staff_only=True)` the thread itself uses. `policy.eligible_handler` is the one
  predicate, shared with `assign_handler`, so the list and the mutation cannot disagree.
* This preserves PR #198 exactly: an ordinary Counselor and their supervised staff handle only
  explicit Colleges; a Head adds the unique-Head fallback Colleges, and staff under a Head get only
  those; a College with another valid Counselor is not inherited through the Head designation;
  several active Heads disable the fallback; inactive or broken supervision fails closed; an override
  removing `guidance_messages.manage` makes a candidate ineligible.
* Search is optional, explicit and matches the safe display name only (never email). The list is not
  the Accounts directory and is not an account search.

**The mutation stays the authority.** The list is advisory. `assign_handler` revalidates the chosen
handler under current workload; a candidate who became ineligible is refused with the existing
bounded `422 invalid_guidance_message_input`, and the frontend refreshes the list. Nothing retries an
assignment automatically. Assignment keeps its existing audit (`guidance_messages.thread.assigned`)
and its existing `messages.thread_changed` hint; there is no new realtime event.

### Message templates

**A template prepares text; it never sends a Message.** `GuidanceMessageTemplate` is reusable plain
text scoped to Guidance Messages, not an institution-wide communication platform. A staff member
chooses one in the composer, its text enters the draft, they edit it freely, and Send creates an
ordinary encrypted `GuidanceMessage` through the unchanged send path. The Message carries no
template ID, type or provenance, and the server does not know a template was used.

**Model.** UUID `id`; `name` (trimmed, one visible line, at most 120 characters, globally unique
ignoring case); `body` (plain UTF-8, nonblank, at most 4,000 characters, NUL and lone surrogates
refused, line breaks and spacing kept exactly); `status` `ACTIVE` or `ARCHIVED`; `created_by`,
`updated_by`, `archived_by` (all `PROTECT`), timestamps and `archived_at`. Database constraints
enforce the archive shape, the case-insensitive name uniqueness, nonblank name and body and the body
length. `default_permissions = ()`. No folders, tags, versions, approval states or merge fields.

**Template text is generic office content, not Student content.** It is shared with Guidance staff
and must never contain a Student's name or details; the editor says so beside the text. It is not
encrypted with the Message keyring, needs no key, and is never classified automatically. It is never
audited.

**Authority.**
* Using (listing active) templates: active Counselor or Guidance Services Staff with
  `guidance_messages.manage`, the same authority that writes operational Messages.
* Managing them: the new capability `guidance_messages.templates.manage` (create, edit, archive,
  restore), which requires `guidance_messages.manage`. Baseline grants: Counselor and Guidance
  Services Staff. Student, IT Admin and Institutional Officer receive none, and no designation grants
  it: a Head manages templates as a Counselor. Overrides can add or remove it; a non-staff role is
  refused even with granted overrides.

**API.** `GET /templates` (`status=ACTIVE` for any template user, `ARCHIVED` only for managers;
optional explicit name-only search; `name` then `id` order; bounded pages), `POST /templates`,
`PATCH /templates/{id}` (active templates only, with an optional `expected_updated_at` that refuses
an edit of a version someone else already changed), `POST /templates/{id}/archive` and
`/restore` (repeating the current state changes and records nothing). There is no delete. Archiving
removes a template from the composer only; sent Messages, existing drafts and audit history do not
change. Audit actions `guidance_messages.template.created|updated|archived|restored` record the
template ID, status and, for edits, the changed field names; never the text.

**No realtime and no persistence.** Template changes publish nothing. Template queries live only in
the in-memory QueryClient, so the account-ownership boundary removes them on an account change, and
same-tab changes invalidate them. No template text reaches storage or a URL.

**Frontend.** The template picker is part of the shared composer (`useMessageComposer.insertTemplate`
and `MessageComposerView`), so the full conversation (Office and the exact Counselor's Counseling
thread), staff New Message and the contextual Counselor panel (including its first Message) get the
same behavior. A blank draft becomes the template; a nonblank draft keeps its text and gets the
template after one blank line, never replaced. A result over 4,000 characters is refused with the
draft unchanged. While a send is in flight or unconfirmed, its exact text and `client_message_id`
belong to its retry, so templates are unavailable until it is confirmed or the reader chooses Edit
message; choosing a template never creates an ID. The page `/portal/messages/templates` (outside the
chat layout) is reachable from Messages only for template managers. No templates are seeded: the
institution has not approved any wording.

## Boundaries and consequences

There is no `TemplateMessage`, automated reply, scheduled or delayed send, broadcast, bulk send,
reminder, rule, AI choice, merge variable or template DSL, and no Task, Case, FollowUp, work queue or
approval workflow. Templates are not added to retention executors (ADR-072) and get no retention
category. No Notification is sent per Message or template. One migration adds the template table;
`GuidanceThread`, `GuidanceMessage` and existing Message data are unchanged.
