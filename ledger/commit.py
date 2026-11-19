from collections.abc import Iterable
import sqlite3

from ledger.changes import FieldChange, validate_changes
from ledger.database import write_transaction
from ledger.fields import FieldKey, FieldState, set_field_value
from ledger.revisions import append_revision


def write_corrections(db: sqlite3.Connection, batch_id: str, changes: Iterable[FieldChange]) -> tuple[FieldState, ...]:
    if not db.in_transaction:
        raise RuntimeError('Field writes require a caller-owned transaction')
    pending = validate_changes(db, batch_id, changes)
    written = []
    for change in pending:
        state = set_field_value(db, change.key, change.expected_revision, change.value)
        append_revision(db, state)
        written.append(state)
    return tuple(written)


def correct(db: sqlite3.Connection, batch_id: str, field_id: str, expected_revision: int, value: int | None) -> FieldState:
    change = FieldChange(FieldKey(batch_id, field_id), expected_revision, value)
    with write_transaction(db):
        state, = write_corrections(db, batch_id, (change,))
        return state
