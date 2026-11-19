from collections.abc import Iterable
from dataclasses import dataclass
import sqlite3

from ledger.fields import FieldKey, StaleRevision, get_field


@dataclass(frozen=True)
class FieldChange:
    key: FieldKey
    expected_revision: int
    value: int | None


def validate_changes(db: sqlite3.Connection, batch_id: str, changes: Iterable[FieldChange]) -> tuple[FieldChange, ...]:
    pending = tuple(changes)
    if not pending:
        raise ValueError('A correction requires at least one field change')
    seen: set[FieldKey] = set()
    for change in pending:
        if change.key.batch_id != batch_id:
            raise ValueError('All field changes must belong to the same batch')
        if change.key in seen:
            raise ValueError(f'Duplicate write target {change.key.field_id!r}')
        seen.add(change.key)
        revision = change.expected_revision
        if type(revision) is not int or revision < 0:
            raise ValueError('Expected revision must be a nonnegative integer')
        if change.value is not None and type(change.value) is not int:
            raise ValueError('Correction must be integer micrometres or null')
        current = get_field(db, change.key)
        if current.revision != revision:
            raise StaleRevision(f'Expected revision {revision} for {change.key.field_id!r}, found {current.revision}')
    return pending
