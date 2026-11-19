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


def _issuance_chain(reference, address: CellAddress) -> tuple[str, tuple[tuple[str, int], ...]]:
    if not isinstance(reference, dict):
        raise InvalidCell(f"Cell {address!r} has no applicable issuance reference")
    source = reference.get("source")
    reads = reference.get("reads")
    if not isinstance(source, str) or not source.strip():
        raise InvalidCell(f"Cell {address!r} has no applicable issuance reference")
    if not isinstance(reads, list) or not reads:
        raise InvalidCell(f"Cell {address!r} has no applicable issuance reference")
    chain = []
    for item in reads:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or not isinstance(item[0], str) or type(item[1]) is not int):
            raise InvalidCell(f"Cell {address!r} has no applicable issuance reference")
        chain.append((item[0], item[1]))
    if chain[-1][0] != source:
        raise InvalidCell(f"Cell {address!r} has no applicable issuance reference")
    return source, tuple(chain)


def qualify_edits(db: sqlite3.Connection, table: FixedTable, edits: tuple[CellEdit, ...]) -> tuple[QualifiedEdit, ...]:
    displayed = {cell.address: cell for cell in table.view.cells}
    qualified = []
    for edit in edits:
        cell = displayed.get(edit.address)
        if cell is None:
            raise InvalidCell(f'Unknown cell {edit.address!r}')
        if cell.value is None:
            raise InvalidCell(f'Blank cell {edit.address!r} has no edit target')
        source, chain = _issuance_chain(table.references.get(edit.address), edit.address)
        for field_id, expected in chain:
            try:
                current = get_field(db, FieldKey(table.view.batch_id, field_id))
            except KeyError as error:
                raise StaleEdit(f"Field {field_id!r} is unavailable for {edit.address!r}") from error
            if current.revision != expected:
                raise StaleEdit(f"Field {field_id!r} changed after issuance of {edit.address!r}")
        qualified.append(QualifiedEdit(edit.address, FieldKey(table.view.batch_id, source), chain[-1][1], edit.value))
    return tuple(qualified)
