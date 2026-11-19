import sqlite3

from issue.store import FixedTable, TableView, fetch_table
from ledger.database import read_transaction


def load_issued_table(db: sqlite3.Connection, table_id: int, *, with_references: bool = True) -> FixedTable:
    if type(table_id) is not int or table_id <= 0:
        raise ValueError('Table number must be a positive integer')
    table = fetch_table(db, table_id, with_references=with_references)
    if table is None:
        raise KeyError(f'Unknown table {table_id}')
    return table


def read_table(db: sqlite3.Connection, table_id: int) -> TableView:
    with read_transaction(db):
        return load_issued_table(db, table_id, with_references=False).view
