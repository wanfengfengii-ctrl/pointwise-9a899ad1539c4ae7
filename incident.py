from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from intake.batch import load
from issue.export import export
from ledger.commit import correct
from ledger.database import open_database
from ledger.fields import list_fields
from ledger.revisions import read_revisions
from returns.eligibility import StaleEdit
from returns.submit import submit


def account(db, batch_id):
    fields = list_fields(db, batch_id)
    history = tuple(read_revisions(db, field.key) for field in fields)
    receipts, = db.execute("SELECT count(*) FROM return_receipts").fetchone()
    return fields, history, receipts


def main():
    sample = Path(__file__).with_name("examples") / "batch.json"
    batch = json.loads(sample.read_text(encoding="utf-8"))
    batch_id = batch["batch_id"]
    with TemporaryDirectory(prefix="fallback-check-") as directory:
        path = Path(directory) / "shift.sqlite"
        with closing(open_database(path)) as db:
            load(db, batch)
            table = export(db, batch_id)
            correct(db, batch_id, "S", 0, 17)
        with closing(open_database(path)) as db:
            before = account(db, batch_id)
            try:
                receipt = submit(db, table.table_id, [{"row": "A", "cell": "effective", "value_um": 19}])
            except StaleEdit:
                if account(db, batch_id) != before:
                    raise AssertionError("Rejected edit changed the field account")
                print("STALE_FALLBACK_REJECTED")
                return 0
            changes = [(state.key.field_id, state.value, state.revision) for state in receipt.changes]
            print("STALE_FALLBACK_ACCEPTED", changes)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
