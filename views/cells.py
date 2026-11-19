from dataclasses import dataclass

from ledger.snapshot import BatchSnapshot
from views.order import CellAddress, PlacedCell
from views.selection import select_reading


@dataclass(frozen=True)
class DisplayCell:
    address: CellAddress
    row_index: int
    cell_index: int
    value: int | None
    nominal_field: str


def project_cells(snapshot: BatchSnapshot, layout: tuple[PlacedCell, ...]) -> tuple[DisplayCell, ...]:
    declared = dict.fromkeys(field_id for placed in layout for field_id in placed.spec.candidates)
    for field_id in declared:
        snapshot.field(field_id)

    def read_value(field_id: str) -> int | None:
        return snapshot.field(field_id).value

    cells = []
    for placed in layout:
        candidates = placed.spec.candidates
        value = select_reading(candidates, read_value)
        cells.append(DisplayCell(placed.address, placed.row_index, placed.cell_index, value, candidates[0]))
    return tuple(cells)
