"""Non-mutating tombstones for the retired in-app disposition tasks (ADR-114).

The task names stay registered for one release so that broker-resident or redelivered messages
from the previous build are acknowledged and dropped instead of failing as unregistered. A
tombstone never reads its arguments, never touches source, case, hold or rule rows, never calls
Daily or object storage, and never enqueues further work. It emits one minimized diagnostic.
"""

import logging

from celery import shared_task

from compass.tasks import CorrelationTask

logger = logging.getLogger("compass.privacy_governance")

DISCOVER_RETENTION = "compass.privacy_governance.discover_retention"
EXECUTE_DISPOSITION = "compass.privacy_governance.execute_disposition"
RECOVER_DISPOSITION = "compass.privacy_governance.recover_disposition"
TOMBSTONE_TASK_NAMES = (DISCOVER_RETENTION, EXECUTE_DISPOSITION, RECOVER_DISPOSITION)


def _decommissioned(task_name):
    # Arguments (for example a case ID) are deliberately never inspected or logged.
    logger.info(
        "retired retention task message dropped",
        extra={
            "event": "retention_task_decommissioned",
            "task_name": task_name,
            "outcome_code": "DECOMMISSIONED",
        },
    )


@shared_task(base=CorrelationTask, name=DISCOVER_RETENTION, ignore_result=True)
def discover_retention(*args, **kwargs):
    _decommissioned(DISCOVER_RETENTION)


@shared_task(base=CorrelationTask, name=EXECUTE_DISPOSITION, ignore_result=True)
def execute_disposition(*args, **kwargs):
    _decommissioned(EXECUTE_DISPOSITION)


@shared_task(base=CorrelationTask, name=RECOVER_DISPOSITION, ignore_result=True)
def recover_disposition(*args, **kwargs):
    _decommissioned(RECOVER_DISPOSITION)
