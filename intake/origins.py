import sqlite3

from intake.parse import DeviceReading
from ledger.fields import decode_reading, encode_reading


def create_origin_schema(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS device_origins (
            batch_id TEXT NOT NULL,
            field_id TEXT NOT NULL,
            device TEXT NOT NULL,
            initial_value_hex TEXT,
            PRIMARY KEY (batch_id, field_id),
            FOREIGN KEY (batch_id, field_id) REFERENCES fields (batch_id, field_id)
        )
    ''')


def record_origins(db: sqlite3.Connection, batch_id: str, readings: tuple[DeviceReading, ...]) -> None:
    db.executemany(
        'INSERT INTO device_origins VALUES (?, ?, ?, ?)',
        ((batch_id, row.field_id, row.device, encode_reading(row.value)) for row in readings),
    )


def read_origins(db: sqlite3.Connection, batch_id: str) -> tuple[DeviceReading, ...]:
    rows = db.execute('''
        SELECT field_id, device, initial_value_hex
        FROM device_origins WHERE batch_id = ? ORDER BY field_id
    ''', (batch_id,))
    return tuple(DeviceReading(field_id, device, decode_reading(value)) for field_id, device, value in rows)
