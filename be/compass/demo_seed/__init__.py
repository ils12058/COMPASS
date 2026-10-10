"""Staging-only, deterministic COMPASS demo dataset seeding.

This package is operator tooling behind the ``seed_demo_staging`` management command. It is not a
runtime feature: no API, middleware, model, or service branches on whether a record was seeded.
"""

DEMO_DATASET_VERSION = 2
