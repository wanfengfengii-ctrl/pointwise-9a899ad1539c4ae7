from collections.abc import Mapping
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class DeviceReading:
    field_id: str
    device: str
    value: int | None


@dataclass(frozen=True)
class DeviceBatch:
    batch_id: str
    readings: tuple[DeviceReading, ...]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate input key {key!r}')
        result[key] = value
    return result


def _identifier(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a nonblank string')
    return value


def _parse_reading(item, position: int) -> DeviceReading:
    if not isinstance(item, Mapping) or set(item) != {'field', 'device', 'value_um'}:
        raise ValueError(f'Invalid device record at position {position}')
    field_id = _identifier(item['field'], 'Field identifier')
    device = _identifier(item['device'], 'Device identifier')
    value = item['value_um']
    if value is not None and type(value) is not int:
        raise ValueError(f'Device reading for {field_id!r} must be integer micrometres or null')
    return DeviceReading(field_id, device, value)


def parse_batch(payload: Mapping | str) -> DeviceBatch:
    if isinstance(payload, str):
        payload = json.loads(payload, object_pairs_hook=_unique_object)
    if not isinstance(payload, Mapping) or set(payload) != {'batch_id', 'readings'}:
        raise ValueError('A batch requires batch_id and readings')
    batch_id = _identifier(payload['batch_id'], 'Batch identifier')
    records = payload['readings']
    if not isinstance(records, list) or not records:
        raise ValueError('Readings must be a nonempty list')
    return DeviceBatch(batch_id, tuple(_parse_reading(item, index) for index, item in enumerate(records)))
