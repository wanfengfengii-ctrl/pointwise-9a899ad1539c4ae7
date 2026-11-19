from dataclasses import dataclass
import sqlite3

from ledger.database import read_transaction
from ledger.fields import FieldKey, FieldState, decode_reading, encode_reading


@dataclass(frozen=True)
class Receipt:
    receipt_id: int
    table_id: int
    changes: tuple[FieldState, ...]

    @property
    def field_count(self) -> int:
        return len(self.changes)


def create_receipt_schema(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS return_receipts (
            receipt_id INTEGER PRIMARY KEY,
            table_id INTEGER NOT NULL REFERENCES issued_tables (table_id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS receipt_fields (
            receipt_id INTEGER NOT NULL REFERENCES return_receipts (receipt_id),
            position INTEGER NOT NULL CHECK (position >= 0),
            field_id TEXT NOT NULL,
            value_hex TEXT,
            revision INTEGER NOT NULL CHECK (revision > 0),
            PRIMARY KEY (receipt_id, position),
            UNIQUE (receipt_id, field_id)
        )
    ''')


def save_receipt(db: sqlite3.Connection, table_id: int, changes: tuple[FieldState, ...]) -> Receipt:
    cursor = db.execute('INSERT INTO return_receipts (table_id) VALUES (?)', (table_id,))
    receipt_id = cursor.lastrowid
    db.executemany('''
        INSERT INTO receipt_fields (receipt_id, position, field_id, value_hex, revision)
        VALUES (?, ?, ?, ?, ?)
    ''', ((receipt_id, position, state.key.field_id, encode_reading(state.value), state.revision)
          for position, state in enumerate(changes)))
    return Receipt(receipt_id, table_id, changes)


def read_receipt(db: sqlite3.Connection, receipt_id: int) -> Receipt:
    if type(receipt_id) is not int or receipt_id <= 0:
        raise ValueError('Receipt number must be a positive integer')
    if receipt_id.bit_length() > 63:
        raise KeyError('Unknown receipt number')
    with read_transaction(db):
        header = db.execute('''
            SELECT receipts.table_id, tables.batch_id FROM return_receipts AS receipts
            JOIN issued_tables AS tables ON tables.table_id = receipts.table_id
            WHERE receipts.receipt_id = ?
        ''', (receipt_id,)).fetchone()
        if header is None:
            raise KeyError(f'Unknown receipt {receipt_id}')
        table_id, batch_id = header
        rows = db.execute('''
            SELECT field_id, value_hex, revision FROM receipt_fields
            WHERE receipt_id = ? ORDER BY position
        ''', (receipt_id,))
        changes = tuple(FieldState(FieldKey(batch_id, field), decode_reading(value), revision)
                        for field, value, revision in rows)
        return Receipt(receipt_id, table_id, changes)
