from collections.abc import Mapping
from dataclasses import dataclass

from views.order import CellAddress


@dataclass(frozen=True)
class CellEdit:
    address: CellAddress
    value: int


@dataclass(frozen=True)
class ReturnRequest:
    table_id: int
    edits: tuple[CellEdit, ...]


def parse_return(table_id: int, edits: list[Mapping]) -> ReturnRequest:
    if type(table_id) is not int or table_id <= 0:
        raise ValueError('Table number must be a positive integer')
    if not isinstance(edits, list) or not edits:
        raise ValueError('A return requires a nonempty list of edits')
    parsed = []
    for index, edit in enumerate(edits):
        if not isinstance(edit, Mapping) or set(edit) != {'row', 'cell', 'value_um'}:
            raise ValueError(f'Invalid return item at position {index}')
        address = CellAddress(edit['row'], edit['cell'])
        value = edit['value_um']
        if type(value) is not int:
            raise ValueError(f'Returned value at {address!r} must be integer micrometres')
        parsed.append(CellEdit(address, value))
    return ReturnRequest(table_id, tuple(parsed))
