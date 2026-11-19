import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from intake.batch import load
from ledger.database import open_database
from ledger.fields import FieldKey, get_field, list_fields
from ledger.revisions import read_revisions


SAMPLE = Path(__file__).resolve().parents[1] / 'examples'
BATCH_ID = 'CW-27'


def sample_batch():
    return json.loads((SAMPLE / 'batch.json').read_text(encoding='utf-8'))


def edit(row, value, cell='effective'):
    return {'row': row, 'cell': cell, 'value_um': value}


def displayed(table):
    return [(cell.address.row, cell.address.column, cell.value) for cell in table.cells]


def install_commit_failure(db, relation):
    # The insert finishes. SQLite checks the missing parent when COMMIT is attempted.
    if relation not in {'registrations', 'issued_tables', 'return_receipts'}:
        raise ValueError('Unknown fixture target')
    db.execute('CREATE TABLE commit_parents (id INTEGER PRIMARY KEY)')
    db.execute('''
        CREATE TABLE commit_children (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER REFERENCES commit_parents(id) DEFERRABLE INITIALLY DEFERRED
        )
    ''')
    db.execute(f'''
        CREATE TRIGGER reject_commit AFTER INSERT ON {relation}
        BEGIN
            INSERT INTO commit_children (parent_id) VALUES (1);
        END
    ''')


def install_receipt_write_failure(db):
    db.execute('''
        CREATE TRIGGER reject_receipt_detail BEFORE INSERT ON receipt_fields
        BEGIN
            SELECT RAISE(ABORT, 'fixture receipt detail rejected');
        END
    ''')


class LabCase(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory(prefix='coating-test-')
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'shift.sqlite'
        self.db = open_database(self.path)
        self.addCleanup(self.close_database)

    def close_database(self):
        if self.db is not None:
            self.db.close()
            self.db = None

    def reopen(self):
        self.close_database()
        self.db = open_database(self.path)

    def register(self):
        return load(self.db, sample_batch())

    def field(self, field_id):
        return get_field(self.db, FieldKey(BATCH_ID, field_id))

    def history(self, field_id):
        return read_revisions(self.db, FieldKey(BATCH_ID, field_id))

    def counts(self, *relations):
        allowed = {'registrations', 'field_scopes', 'fields', 'device_origins', 'field_revisions',
                   'issued_tables', 'issued_cells', 'return_receipts', 'receipt_fields', 'commit_children'}
        if not set(relations) <= allowed:
            raise ValueError('Unknown fixture relation')
        return tuple(self.db.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in relations)

    def account(self):
        fields = list_fields(self.db, BATCH_ID)
        histories = tuple(read_revisions(self.db, field.key) for field in fields)
        return fields, histories, self.counts('return_receipts', 'receipt_fields')
