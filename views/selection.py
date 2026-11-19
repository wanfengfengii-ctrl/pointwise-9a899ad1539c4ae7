from collections.abc import Callable, Iterable


def trace_reading(candidates: Iterable[str], read_value: Callable[[str], int | None]) -> tuple[int | None, tuple[str, ...]]:
    read = []
    for field_id in candidates:
        read.append(field_id)
        value = read_value(field_id)
        if value is not None:
            return value, tuple(read)
    return None, tuple(read)


def select_reading(candidates: Iterable[str], read_value: Callable[[str], int | None]) -> int | None:
    value, _ = trace_reading(candidates, read_value)
    return value
