"""Which local-time slot each scheduled video takes."""

import datetime


def _parse_slot_times(slot_times: list[str]) -> list[datetime.time]:
    """Parse and sort HH:MM strings into time objects."""
    parsed = sorted(
        datetime.time(int(h), int(m)) for h, m in (s.split(":") for s in slot_times)
    )
    if not parsed:
        raise ValueError("publish_slots_local must contain at least one HH:MM entry")
    return parsed


def next_publish_slot(
    after: datetime.datetime,
    slot_times: list[str],
    min_lead_minutes: int,
    *,
    _now: datetime.datetime | None = None,
) -> datetime.datetime:
    """Return the first eligible slot strictly after *after*.

    Respects *min_lead_minutes* relative to the real clock (now), and
    also ensures the slot comes after the previous scheduled time so
    slots never go backwards.
    """
    parsed = _parse_slot_times(slot_times)
    now = _now or datetime.datetime.now()
    earliest = max(
        after + datetime.timedelta(minutes=1),
        now + datetime.timedelta(minutes=min_lead_minutes),
    )
    day = earliest.date()

    for _ in range(400):
        for t in parsed:
            candidate = datetime.datetime.combine(day, t)
            if candidate >= earliest:
                return candidate
        day += datetime.timedelta(days=1)

    raise RuntimeError("Could not find a valid publish slot within 400 days")


def compute_publish_slots(
    now: datetime.datetime,
    slot_times: list[str],
    count: int,
    min_lead_minutes: int,
) -> list[datetime.datetime]:
    """Return the next *count* eligible local-time publish slots starting from *now*.

    Walks configured HH:MM slots forward day-by-day, skipping any slot
    that falls within *min_lead_minutes* of *now*.
    """
    parsed = _parse_slot_times(slot_times)
    earliest = now + datetime.timedelta(minutes=min_lead_minutes)
    day = now.date()
    slots: list[datetime.datetime] = []

    while len(slots) < count:
        for t in parsed:
            candidate = datetime.datetime.combine(day, t)
            if candidate >= earliest and len(slots) < count:
                slots.append(candidate)
        day += datetime.timedelta(days=1)

    return slots
