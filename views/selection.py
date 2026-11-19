from collections.abc import Callable, Iterable


def select_reading(candidates: Iterable[str], read_value: Callable[[str], int | None]) -> int | None:
    for field_id in candidates:
        value = read_value(field_id)
        if value is not None:
            return value
    return None
