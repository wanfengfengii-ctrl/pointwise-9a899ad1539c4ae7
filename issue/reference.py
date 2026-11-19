from ledger.snapshot import BatchSnapshot
from views.order import CellAddress, PlacedCell
from views.selection import trace_reading


def freeze_references(snapshot: BatchSnapshot, layout: tuple[PlacedCell, ...]) -> dict[CellAddress, dict[str, object]]:
    references = {}
    for placed in layout:
        candidates = placed.spec.candidates
        value, chain = trace_reading(candidates, lambda field_id: snapshot.field(field_id).value)
        references[placed.address] = {
            "source": chain[-1] if value is not None else None,
            "reads": [[field_id, snapshot.field(field_id).revision] for field_id in chain],
        }
    return references
