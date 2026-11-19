import sqlite3

from issue.reference import freeze_references
from issue.store import TableView, save_table
from ledger.database import write_transaction
from ledger.snapshot import read_batch_snapshot
from views.cells import project_cells
from views.order import resolve_layout
from views.roster import Roster, configured_roster


def export(db: sqlite3.Connection, batch_id: str, *, roster: Roster | None = None) -> TableView:
    if not isinstance(batch_id, str) or not batch_id.strip():
        raise ValueError('Batch identifier must be a nonblank string')
    layout = resolve_layout(configured_roster() if roster is None else roster)
    with write_transaction(db):
        snapshot = read_batch_snapshot(db, batch_id)
        cells = project_cells(snapshot, layout)
        references = freeze_references(snapshot, layout)
        return save_table(db, batch_id, cells, references)
