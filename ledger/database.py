from contextlib import contextmanager
from os import PathLike
import sqlite3


@contextmanager
def _transaction(db: sqlite3.Connection, begin: str):
    db.execute(begin)
    try:
        yield db
        db.commit()
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise


def read_transaction(db: sqlite3.Connection):
    return _transaction(db, 'BEGIN')


def write_transaction(db: sqlite3.Connection):
    return _transaction(db, 'BEGIN IMMEDIATE')


def open_database(path: str | PathLike[str]) -> sqlite3.Connection:
    from intake.origins import create_origin_schema
    from intake.registration import create_registration_schema
    from issue.store import create_table_schema
    from ledger.fields import create_field_schema
    from ledger.revisions import create_revision_schema
    from returns.receipts import create_receipt_schema

    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.execute('PRAGMA foreign_keys = ON')
        with write_transaction(db):
            create_registration_schema(db)
            create_field_schema(db)
            create_origin_schema(db)
            create_revision_schema(db)
            create_table_schema(db)
            create_receipt_schema(db)
    except BaseException:
        db.close()
        raise
    return db
