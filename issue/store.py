from collections.abc import Mapping
from dataclasses import dataclass
import json
import sqlite3
from types import MappingProxyType

from ledger.fields import FieldKey, decode_reading, encode_reading
from views.cells import DisplayCell
from views.order import CellAddress


@dataclass(frozen=True)
class TableView:
    table_id: int
    batch_id: str
    cells: tuple[DisplayCell, ...]


@dataclass(frozen=True)
class FixedTable:
    view: TableView
    references: Mapping[CellAddress, Mapping[str, object]]


def create_table_schema(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS issued_tables (
            table_id INTEGER PRIMARY KEY,
            batch_id TEXT NOT NULL REFERENCES field_scopes (batch_id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS issued_cells (
            table_id INTEGER NOT NULL REFERENCES issued_tables (table_id),
            row_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            row_position INTEGER NOT NULL CHECK (row_position >= 0),
            cell_position INTEGER NOT NULL CHECK (cell_position >= 0),
            nominal_field TEXT NOT NULL,
            value_hex TEXT,
            reference_json TEXT,
            PRIMARY KEY (table_id, row_name, column_name),
            UNIQUE (table_id, row_position, cell_position)
        )
    ''')


def save_table(db: sqlite3.Connection, batch_id: str, cells: tuple[DisplayCell, ...],
               references: Mapping[CellAddress, Mapping[str, object]]) -> TableView:
    cursor = db.execute('INSERT INTO issued_tables (batch_id) VALUES (?)', (batch_id,))
    table_id = cursor.lastrowid
    records = []
    for cell in cells:
        reference = references[cell.address]
        records.append((table_id, cell.address.row, cell.address.column, cell.row_index, cell.cell_index,
                        cell.nominal_field, encode_reading(cell.value), json.dumps(reference, separators=(",", ":"))))
    db.executemany('''
        INSERT INTO issued_cells (table_id, row_name, column_name, row_position, cell_position,
                                  nominal_field, value_hex, reference_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', records)
    return TableView(table_id, batch_id, cells)


def fetch_table(db: sqlite3.Connection, table_id: int, *, with_references: bool = True) -> FixedTable | None:
    if table_id.bit_length() > 63:
        return None
    header = db.execute('SELECT batch_id FROM issued_tables WHERE table_id = ?', (table_id,)).fetchone()
    if header is None:
        return None
    batch_id, = header
    records = db.execute('''
        SELECT row_name, column_name, row_position, cell_position, nominal_field, value_hex, reference_json
        FROM issued_cells WHERE table_id = ? ORDER BY row_position, cell_position
    ''', (table_id,))
    cells = []
    references = {}
    for row, column, row_index, cell_index, nominal, value, reference_json in records:
        address = CellAddress(row, column)
        cells.append(DisplayCell(address, row_index, cell_index, decode_reading(value), nominal))
        if with_references and reference_json is not None:
            references[address] = json.loads(reference_json)
    return FixedTable(TableView(table_id, batch_id, tuple(cells)), MappingProxyType(references))
