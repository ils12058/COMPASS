"""COMPASS Staging Dataset v1: the staging-only, deterministic, UAT-ready synthetic dataset.

This package is operator tooling behind the ``seed_staging_dataset`` management command. It is not
a runtime feature: no API, middleware, model, or service branches on whether a record was seeded.

Dataset v1 is a new lineage built for the canonical (CANON-1C) baseline. It does not upgrade or
recognize the retired Demo Dataset v1/v2 (``seed_demo_staging``). The dataset version is
independent of the COMPASS application and API versions.
"""

DATASET_NAME = "COMPASS Staging Dataset v1"
DATASET_VERSION = 1
# Stable namespace for idempotency keys and request fingerprints written by this lineage.
DATASET_NAMESPACE = "staging-dataset-v1"
