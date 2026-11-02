"""The ageing of the debt: how old it is, and which ribbon it belongs to.

PA-03 asks for two things, and this module provides exactly them.

**The age of a charge.** `age_in_days(occurred_at, at)` is the calendar-day
difference between the instant the charge happened and the instant the
question is asked. The two values arrive **shop-local**: the service layer is
the only place that converts UTC to the shop's calendar days, so a "day" here
is a calendar day of the shop and never a 86,400-second block. The caller
always passes `at` — there is no implicit clock.

**The ribbon.** `bucket_of(age_days)` sorts the age into one of the four
buckets, at the boundaries PA-03 fixes:

| Bucket    | Age of the `cargo` |
| --------- | ------------------ |
| `vigente` | ≤ 7 d              |
| `envejecido` | 8–30 d          |
| `viejo`    | 31–90 d             |
| `cronico`  | > 90 d              |

A charge is bucketed by **its own** age, so the four bucket totals are a
partition of the same unpaid charges — they sum exactly to the outstanding
and are never a separate figure.
"""

from __future__ import annotations

from datetime import date, datetime

from .types import Bucket

# The inclusive upper bound of each bucket, in days. A charge whose age is
# at most `VIGENTE_HASTA` days is `vigente`, at most `ENVEJECIDO_HASTA` is
# `envejecido`, and at most `VIEJO_HASTA` is `viejo`; anything older is
# `cronico`. The boundaries are the ones PA-03 fixes: 7/8, 30/31 and 90/91.
VIGENTE_HASTA = 7
ENVEJECIDO_HASTA = 30
VIEJO_HASTA = 90


def age_in_days(occurred_at, at) -> int:
    """The calendar-day age of `occurred_at` measured at `at`.

    The difference is taken between the two **dates**, not between the two
    instants, so a charge made at 23:50 and read at 00:10 the next morning is
    one day old, not zero. The caller passes shop-local values, so the day
    boundary is the shop's calendar day.

    A charge that has not happened yet — `occurred_at` after `at` — has a
    negative age. The age is reported as it is; no rule clamps it, because
    the service layer never admits a future charge in the first place.
    """
    occurred = _as_date(occurred_at)
    reference = _as_date(at)
    return (reference - occurred).days


def bucket_of(age_days: int) -> Bucket:
    """The ribbon an age of `age_days` days belongs to.

    The boundaries are the ones PA-03 fixes, and each of them is inclusive at
    its lower end: 7 days is still `vigente`, 8 is `envejecido`; 30 is
    `envejecido`, 31 is `viejo`; 90 is `viejo`, 91 is `cronico`.

    A negative age — a charge dated in the future — falls into `vigente`,
    which is the bucket of the youngest charge in the table.
    """
    if age_days <= VIGENTE_HASTA:
        return Bucket.VIGENTE
    if age_days <= ENVEJECIDO_HASTA:
        return Bucket.ENVEJECIDO
    if age_days <= VIEJO_HASTA:
        return Bucket.VIEJO
    return Bucket.CRONICO


def _as_date(value) -> date:
    """The calendar day of `value`, whichever shape the caller used.

    The service layer may hand over a `datetime` or a plain `date`; both
    describe a shop-local calendar day, and the difference is taken between
    the days.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(
        f"expected a date or a datetime, got {type(value).__name__}"
    )
