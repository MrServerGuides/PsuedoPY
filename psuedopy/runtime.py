from __future__ import annotations

from collections.abc import Iterator


def inclusive_range(start: int, end: int, step: int = 1) -> range:
    """Return a pseudocode-style inclusive integer range."""

    if not all(isinstance(value, int) for value in (start, end, step)):
        raise TypeError("Repeat range bounds and Step must be integers")
    if step == 0:
        raise ValueError("Repeat Step cannot be zero")
    if start < end and step < 0:
        raise ValueError("Repeat Step must be positive when counting upward")
    if start > end and step > 0:
        raise ValueError("Repeat Step must be negative when counting downward")
    stop = end + (1 if step > 0 else -1)
    return range(start, stop, step)


def repeat_times(count: int) -> Iterator[int]:
    """Validate and implement `Repeat n Times`."""

    if not isinstance(count, int):
        raise TypeError("Repeat count must be an integer")
    if count < 0:
        raise ValueError("Repeat count cannot be negative")
    return iter(range(count))
