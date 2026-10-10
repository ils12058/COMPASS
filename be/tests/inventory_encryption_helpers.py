"""Explicit test fixture storage boundary; no model crypto defaults or hooks."""

from compass.inventory.confidential_content import (
    FIELDS,
    PROJECTIONS,
    read_confidential_content,
    write_confidential_content,
)


def create_inventory_row(model, **values):
    fields = FIELDS[model.__name__]
    payload = PROJECTIONS[model.__name__]().payload()
    payload.update({name: value for name, value in values.items() if name in fields})
    row = model(**{name: value for name, value in values.items() if name not in fields})
    write_confidential_content(row, payload)
    row.save(force_insert=True)
    return row


def update_inventory_private(row, **values):
    payload = read_confidential_content(row).payload()
    payload.update(values)
    write_confidential_content(row, payload)
    row.save(update_fields=["confidential_content_ciphertext"])


def update_inventory_row(queryset, **values):
    """Preserve explicit storage shape for legacy-snapshot fixtures."""
    count = 0
    fields = FIELDS[queryset.model.__name__]
    for row in queryset:
        payload = read_confidential_content(row).payload()
        payload.update({name: value for name, value in values.items() if name in fields})
        write_confidential_content(row, payload)
        queryset.filter(pk=row.pk).update(
            **{name: value for name, value in values.items() if name not in fields},
            confidential_content_ciphertext=row.confidential_content_ciphertext,
        )
        count += 1
    return count
