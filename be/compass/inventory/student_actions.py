"""Structural current-year self-service attention; Inventory owns eligibility."""

from compass.accounts.services import is_current_student

from .services import (
    CurrentAcademicYearNotConfigured,
    InventoryStatus,
    get_current_inventory_status,
)


def current_action(*, student):
    if not is_current_student(student) or not student.has_capability("inventory.manage_self"):
        return None
    try:
        status = get_current_inventory_status(student, structural=True)
    except CurrentAcademicYearNotConfigured:
        return None
    return status if status.status != InventoryStatus.SUBMITTED else None
