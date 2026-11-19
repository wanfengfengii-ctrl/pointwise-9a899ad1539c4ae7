import sqlite3

from ledger.fields import FieldKey, FieldState, decode_reading, encode_reading, get_field


def create_revision_schema(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS field_revisions (
            batch_id TEXT NOT NULL,
            field_id TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 0),
            value_hex TEXT,
            PRIMARY KEY (batch_id, field_id, revision),
            FOREIGN KEY (batch_id, field_id) REFERENCES fields (batch_id, field_id)
        )
    ''')


def _revision_values(state: FieldState) -> tuple:
    return state.key.batch_id, state.key.field_id, state.revision, encode_reading(state.value)


def record_initial_revisions(db: sqlite3.Connection, states: tuple[FieldState, ...]) -> None:
    db.executemany('INSERT INTO field_revisions VALUES (?, ?, ?, ?)', map(_revision_values, states))


def append_revision(db: sqlite3.Connection, state: FieldState) -> None:
    db.execute('INSERT INTO field_revisions VALUES (?, ?, ?, ?)', _revision_values(state))


def read_revisions(db: sqlite3.Connection, key: FieldKey) -> tuple[FieldState, ...]:
    rows = db.execute('''
        SELECT revision, value_hex FROM field_revisions
        WHERE batch_id = ? AND field_id = ? ORDER BY revision
    ''', (key.batch_id, key.field_id))
    history = tuple(FieldState(key, decode_reading(value), revision) for revision, value in rows)
    if not history:
        get_field(db, key)
        raise sqlite3.IntegrityError(f'No revision for registered field {key.field_id!r}')
    return history
