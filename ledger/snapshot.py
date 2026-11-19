from collections.abc import Mapping
from dataclasses import dataclass
import sqlite3
from types import MappingProxyType

from ledger.fields import FieldState, has_field_scope, list_fields


@dataclass(frozen=True)
class BatchSnapshot:
    batch_id: str
    fields: Mapping[str, FieldState]

    def field(self, field_id: str) -> FieldState:
        try:
            return self.fields[field_id]
        except KeyError as error:
            raise KeyError(f'Unknown field {field_id!r} in batch {self.batch_id!r}') from error


def read_batch_snapshot(db: sqlite3.Connection, batch_id: str) -> BatchSnapshot:
    if not db.in_transaction:
        raise RuntimeError('A batch snapshot requires an active transaction')
    if not has_field_scope(db, batch_id):
        raise KeyError(f'Unknown batch {batch_id!r}')
    fields = {field.key.field_id: field for field in list_fields(db, batch_id)}
    return BatchSnapshot(batch_id, MappingProxyType(fields))
