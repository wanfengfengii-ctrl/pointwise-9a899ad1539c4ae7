from collections.abc import Mapping
from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True, order=True)
class FieldKey:
    batch_id: str
    field_id: str

    def __post_init__(self):
        for label, value in (('Batch', self.batch_id), ('Field', self.field_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{label} identifier must be a nonblank string')


@dataclass(frozen=True)
class FieldState:
    key: FieldKey
    value: int | None
    revision: int


class StaleRevision(ValueError):
    pass


def encode_reading(value: int | None) -> str | None:
    if value is None:
        return None
    if type(value) is not int:
        raise ValueError('Reading must be integer micrometres or null')
    return format(value, 'x')


def decode_reading(text: str | None) -> int | None:
    if text is None:
        return None
    return int(text, 16)


def create_field_schema(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS field_scopes (
            batch_id TEXT PRIMARY KEY NOT NULL REFERENCES registrations (batch_id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS fields (
            batch_id TEXT NOT NULL REFERENCES field_scopes (batch_id),
            field_id TEXT NOT NULL,
            value_hex TEXT,
            revision INTEGER NOT NULL CHECK (revision >= 0),
            PRIMARY KEY (batch_id, field_id)
        )
    ''')


def open_field_scope(db: sqlite3.Connection, batch_id: str) -> None:
    db.execute('INSERT INTO field_scopes (batch_id) VALUES (?)', (batch_id,))


def has_field_scope(db: sqlite3.Connection, batch_id: str) -> bool:
    return db.execute('SELECT 1 FROM field_scopes WHERE batch_id = ?', (batch_id,)).fetchone() is not None


def insert_fields(db: sqlite3.Connection, batch_id: str, readings: Mapping[str, int | None]) -> tuple[FieldState, ...]:
    states = tuple(FieldState(FieldKey(batch_id, field_id), value, 0) for field_id, value in readings.items())
    db.executemany(
        'INSERT INTO fields (batch_id, field_id, value_hex, revision) VALUES (?, ?, ?, ?)',
        ((batch_id, state.key.field_id, encode_reading(state.value), state.revision) for state in states),
    )
    return states


def get_field(db: sqlite3.Connection, key: FieldKey) -> FieldState:
    row = db.execute('''
        SELECT value_hex, revision FROM fields WHERE batch_id = ? AND field_id = ?
    ''', (key.batch_id, key.field_id)).fetchone()
    if row is None:
        raise KeyError(key)
    return FieldState(key, decode_reading(row[0]), row[1])


def list_fields(db: sqlite3.Connection, batch_id: str) -> tuple[FieldState, ...]:
    rows = db.execute('''
        SELECT field_id, value_hex, revision FROM fields WHERE batch_id = ? ORDER BY field_id
    ''', (batch_id,))
    return tuple(FieldState(FieldKey(batch_id, name), decode_reading(value), revision) for name, value, revision in rows)


def set_field_value(db: sqlite3.Connection, key: FieldKey, expected_revision: int, value: int | None) -> FieldState:
    next_revision = expected_revision + 1
    cursor = db.execute('''
        UPDATE fields SET value_hex = ?, revision = ?
        WHERE batch_id = ? AND field_id = ? AND revision = ?
    ''', (encode_reading(value), next_revision, key.batch_id, key.field_id, expected_revision))
    if cursor.rowcount != 1:
        raise StaleRevision(f'Expected revision {expected_revision} for {key.field_id!r}')
    return FieldState(key, value, next_revision)
