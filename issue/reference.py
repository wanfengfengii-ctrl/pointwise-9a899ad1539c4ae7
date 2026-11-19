from ledger.snapshot import BatchSnapshot
from views.order import CellAddress, PlacedCell


def freeze_references(snapshot: BatchSnapshot, layout: tuple[PlacedCell, ...]) -> dict[CellAddress, dict[str, int]]:
    return {
        placed.address: {"revision": snapshot.field(placed.spec.candidates[0]).revision}
        for placed in layout
    }
