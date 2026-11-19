from collections.abc import Mapping
import sqlite3

from issue.read import load_issued_table
from ledger.commit import write_corrections
from ledger.database import write_transaction
from returns.eligibility import qualify_edits
from returns.merge import merge_edits
from returns.receipts import Receipt, save_receipt
from returns.request import parse_return


def submit(db: sqlite3.Connection, table_id: int, edits: list[Mapping]) -> Receipt:
    request = parse_return(table_id, edits)
    with write_transaction(db):
        table = load_issued_table(db, request.table_id)
        qualified = qualify_edits(db, table, request.edits)
        changes = merge_edits(qualified)
        written = write_corrections(db, table.view.batch_id, changes)
        return save_receipt(db, table.view.table_id, written)
