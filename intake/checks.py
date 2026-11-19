from collections.abc import Iterable

from intake.parse import DeviceReading


def normalize_readings(readings: Iterable[DeviceReading]) -> tuple[DeviceReading, ...]:
    by_field: dict[str, DeviceReading] = {}
    for reading in readings:
        previous = by_field.get(reading.field_id)
        if previous is None:
            by_field[reading.field_id] = reading
        elif previous != reading:
            raise ValueError(f'Conflicting device records for {reading.field_id!r}')
    return tuple(by_field[field_id] for field_id in sorted(by_field))
