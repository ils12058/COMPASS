# ADR-007: One environment-driven settings contract

## Context

local-staging and live-staging should behave alike where possible while using different external
services and security posture. Forked settings modules tend to drift.

## Decision

Use one `config.settings` module driven by `APP_ENV`, with mandatory secrets and service URLs
validated at import time. Local-only MinIO and Mailpit are Compose profile services; live-staging
must provide external object storage and real SMTP. API docs default on locally and off live.

## Consequences

Configuration errors fail fast. Secrets stay in deployment environment files/secret stores and
are not committed. Environment helpers accept either `SETTING_NAME` or
`SETTING_NAME_FILE=/run/secrets/name`; they reject two non-empty sources and report file errors
without disclosing the path or contents. A Compose secret must be mounted into every application
service that needs the setting. Differences are visible in `.env.example`, Compose profiles, and
deployment checks rather than hidden in code branches.
