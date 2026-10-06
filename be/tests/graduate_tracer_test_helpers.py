"""Explicit synthetic encrypted fixtures; never an ORM interception."""

from compass.graduate_tracer.confidential_content import (
    FIELDS,
    PROJECTIONS,
    write_confidential_content,
)


def encrypted_row(model, **values):
    family = model.__name__
    private = PROJECTIONS[family]().payload()
    for name in FIELDS[family]:
        if name in values:
            private[name] = values.pop(name)
    row = model(**values)
    write_confidential_content(row, private)
    row.save()
    return row
