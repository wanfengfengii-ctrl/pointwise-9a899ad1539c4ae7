from dataclasses import dataclass

from views.roster import CellSpec, Roster


@dataclass(frozen=True)
class CellAddress:
    row: str
    column: str

    def __post_init__(self):
        if any(not isinstance(name, str) or not name.strip() for name in (self.row, self.column)):
            raise ValueError('Row and cell names must be nonblank strings')


@dataclass(frozen=True)
class PlacedCell:
    address: CellAddress
    row_index: int
    cell_index: int
    spec: CellSpec


def resolve_layout(roster: Roster) -> tuple[PlacedCell, ...]:
    seen_rows: set[str] = set()
    placed = []
    for row_index, row in enumerate(roster.rows):
        if row.name in seen_rows:
            raise ValueError(f'Duplicate roster row {row.name!r}')
        seen_rows.add(row.name)
        seen_columns: set[str] = set()
        for cell_index, spec in enumerate(row.cells):
            if spec.column in seen_columns:
                raise ValueError(f'Duplicate cell {spec.column!r} in row {row.name!r}')
            seen_columns.add(spec.column)
            placed.append(PlacedCell(CellAddress(row.name, spec.column), row_index, cell_index, spec))
    if not placed:
        raise ValueError('A roster must contain at least one cell')
    return tuple(placed)
