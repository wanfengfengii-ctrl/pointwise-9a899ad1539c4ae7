from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class RegistrationReceipt:
    registration_id: int
    batch_id: str
    field_count: int


def create_registration_schema(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            registration_id INTEGER PRIMARY KEY,
            batch_id TEXT NOT NULL UNIQUE,
            field_count INTEGER NOT NULL CHECK (field_count > 0)
        )
    ''')


def find_registration(db: sqlite3.Connection, batch_id: str) -> RegistrationReceipt | None:
    row = db.execute(
        'SELECT registration_id, field_count FROM registrations WHERE batch_id = ?',
        (batch_id,),
    ).fetchone()
    if row is None:
        return None
    return RegistrationReceipt(row[0], batch_id, row[1])


def save_registration(db: sqlite3.Connection, batch_id: str, field_count: int) -> RegistrationReceipt:
    row = db.execute(
        'INSERT INTO registrations (batch_id, field_count) VALUES (?, ?)',
        (batch_id, field_count),
    )
    return RegistrationReceipt(row.lastrowid, batch_id, field_count)
