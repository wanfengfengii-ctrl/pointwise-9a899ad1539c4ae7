from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class CellSpec:
    column: str
    kind: str
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class RosterRow:
    name: str
    cells: tuple[CellSpec, ...]


@dataclass(frozen=True)
class Roster:
    rows: tuple[RosterRow, ...]


def _name(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a nonblank string')
    return value


def _items(value, label: str) -> list:
    if not isinstance(value, list) or not value:
        raise ValueError(f'{label} must be a nonempty list')
    return value


def _build_cell(raw: Mapping) -> CellSpec:
    if not isinstance(raw, Mapping):
        raise ValueError('A cell definition must be an object')
    column = _name(raw.get('cell'), 'Cell name')
    kind = raw.get('kind')
    if kind == 'effective' and set(raw) == {'cell', 'kind', 'primary', 'backup'}:
        primary = _name(raw['primary'], 'Primary field')
        backup = _name(raw['backup'], 'Backup field')
        if primary == backup:
            raise ValueError(f'Cell {column!r} needs distinct primary and backup fields')
        return CellSpec(column, kind, (primary, backup))
    if kind == 'direct' and set(raw) == {'cell', 'kind', 'field'}:
        return CellSpec(column, kind, (_name(raw['field'], 'Direct field'),))
    raise ValueError(f'Invalid candidate definition for cell {column!r}')


def build_roster(payload: Mapping) -> Roster:
    if not isinstance(payload, Mapping) or set(payload) != {'rows'}:
        raise ValueError('A roster requires rows')
    rows = []
    for raw in _items(payload['rows'], 'Roster rows'):
        if not isinstance(raw, Mapping) or set(raw) != {'row', 'cells'}:
            raise ValueError('A roster row requires row and cells')
        name = _name(raw['row'], 'Row name')
        cells = tuple(_build_cell(item) for item in _items(raw['cells'], 'Roster cells'))
        rows.append(RosterRow(name, cells))
    return Roster(tuple(rows))


def configured_roster() -> Roster:
    path = Path(__file__).resolve().parents[1] / 'examples' / 'roster.json'
    with path.open(encoding='utf-8') as source:
        return build_roster(json.load(source))
