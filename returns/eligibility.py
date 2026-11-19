from dataclasses import dataclass
import sqlite3

from issue.store import FixedTable
from ledger.fields import FieldKey, get_field
from returns.request import CellEdit
from views.order import CellAddress


class InvalidCell(ValueError):
    pass


class StaleEdit(ValueError):
    pass


@dataclass(frozen=True)
class QualifiedEdit:
    address: CellAddress
    target: FieldKey
    expected_revision: int
    value: int


def qualify_edits(db: sqlite3.Connection, table: FixedTable, edits: tuple[CellEdit, ...]) -> tuple[QualifiedEdit, ...]:
    displayed = {cell.address: cell for cell in table.view.cells}
    qualified = []
    for edit in edits:
        cell = displayed.get(edit.address)
        if cell is None:
            raise InvalidCell(f'Unknown cell {edit.address!r}')
        if cell.value is None:
            raise InvalidCell(f'Blank cell {edit.address!r} has no edit target')
        reference = table.references.get(edit.address)
        if not isinstance(reference, dict) or type(reference.get("revision")) is not int:
            raise InvalidCell(f"Cell {edit.address!r} has no applicable issuance reference")
        expected = reference["revision"]
        target = FieldKey(table.view.batch_id, cell.nominal_field)
        try:
            current = get_field(db, target)
        except KeyError as error:
            raise StaleEdit(f"Field {target.field_id!r} is unavailable for {edit.address!r}") from error
        if current.revision != expected:
            raise StaleEdit(f"Field {target.field_id!r} changed after issuance of {edit.address!r}")
        qualified.append(QualifiedEdit(edit.address, target, expected, edit.value))
    return tuple(qualified)
