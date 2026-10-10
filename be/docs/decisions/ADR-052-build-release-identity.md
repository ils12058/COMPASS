# ADR-052: Build and Release Identity

- **Status:** Accepted
- **Date:** 2026-09-20

## Context

COMPASS staging uses an immutable Git-SHA-tagged container image built by GitHub Actions,
stored in DigitalOcean Container Registry, and deployed to the staging Droplet. Health checks
can prove that an application is serving, but they do not identify which exact source build is
serving.

UAT issue reports, deployment verification, staging troubleshooting, demonstrations, and rollback
analysis need a small safe identity that is available without coupling build traceability to the
database or other runtime dependencies.

## Decision

The pyproject [project].version field is the canonical COMPASS application semantic version.
It is deliberately managed independently from deployments and is not auto-bumped per commit.

The version-one HTTP API contract has its own independent source-controlled API_VERSION. API
version and application semantic version are not derived from each other.

The full 40-character Git commit SHA used to build an image is the canonical Build ID. GitHub
Actions injects that exact DEPLOY_SHA and a UTC build timestamp into the container image. The
timestamp represents artifact build time, not process startup or deployment time.

Live staging fails during Django settings startup when Build ID is not a full lowercase Git SHA
or when the UTC build timestamp is missing or malformed. Local staging may use build_id=local
with no build timestamp.

The backend image carries OCI title, description, source, revision, version, and created labels.
The DigitalOcean registry digest remains the exact registry artifact identity; it is deployment
metadata and is not exposed by the application.

GET /api/v1/meta is intentionally public, read-only, dependency-free, and non-cacheable. It
returns only application name, application version, API version, Build ID, build timestamp, and
environment mode. It remains available during Maintenance Mode.

The existing /api/v1/health/live and /api/v1/health/ready contracts remain unchanged. Build
identity is metadata, not health.

Authenticated Platform Operations reuses the same build-metadata resolver for its Application
environment diagnostics. No new capability is introduced.

After a staging image is pushed, the deployment workflow verifies its OCI revision/version/created
labels. After the deployed candidate is healthy, the workflow calls /api/v1/meta and requires
the running Build ID to equal the intended DEPLOY_SHA and the semantic version to equal the
version read from pyproject.toml.

## Consequences

- No database model, migration, cache record, or deployment registry is introduced.
- No application secret is serialized into public metadata or OCI labels.
- Local development does not require a CI-generated Git SHA.
- Many deployments may legitimately share one semantic application version while having different
  Build IDs.
- The invariant for live staging is: intended Git SHA = image revision identity = running Build ID.
