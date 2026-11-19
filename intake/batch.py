from collections.abc import Mapping
import sqlite3

from intake.checks import normalize_readings
from intake.origins import read_origins, record_origins
from intake.parse import parse_batch
from intake.registration import RegistrationReceipt, find_registration, save_registration
from ledger.database import write_transaction
from ledger.fields import insert_fields, open_field_scope
from ledger.revisions import record_initial_revisions


def load(db: sqlite3.Connection, payload: Mapping | str) -> RegistrationReceipt:
    batch = parse_batch(payload)
    readings = normalize_readings(batch.readings)
    with write_transaction(db):
        existing = find_registration(db, batch.batch_id)
        if existing is not None:
            if read_origins(db, batch.batch_id) != readings:
                raise ValueError(f'Batch {batch.batch_id!r} conflicts with its original registration')
            return existing

        receipt = save_registration(db, batch.batch_id, len(readings))
        open_field_scope(db, batch.batch_id)
        fields = insert_fields(db, batch.batch_id, {row.field_id: row.value for row in readings})
        record_origins(db, batch.batch_id, readings)
        record_initial_revisions(db, fields)
        return receipt
