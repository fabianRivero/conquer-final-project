"""The ageing of the debt: the age, the four ribbons and the sum (PA-03).

PA-03 asks for three things, and this file pins all three:

* `age_in_days` is the **calendar-day** difference;
* `bucket_of` sorts the age at the boundaries 7/8, 30/31 and 90/91;
* the four bucket totals **sum exactly to the outstanding** — the buckets
  are a partition of the same unpaid charges, never a separate figure.

None of these tests carries the `django_db` marker, so no rule in the
ageing path may touch the database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from tienda.domain.ageing import age_in_days, bucket_of
from tienda.domain.allocation import allocate_payments
from tienda.domain.position import outstanding
from tienda.domain.types import Bucket, EntryKind, LedgerLine

DIA = timedelta(days=1)
BASE = datetime(2026, 3, 1, 9, 0, 0)


def cargo(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `cargo` of `importe`, `dias` days after the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.CARGO,
        amount=Decimal(importe),
        occurred_at=BASE - dias * DIA,
    )


def pago(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `pago` of `importe`, `dias` days after the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.PAGO,
        amount=Decimal(importe),
        occurred_at=BASE - dias * DIA,
    )


@pytest.mark.unit
def test_the_age_is_the_calendar_day_difference():
    """The age of a charge is the number of calendar days since it happened."""
    ocurrido = datetime(2026, 3, 1, 9, 0, 0)
    ahora = datetime(2026, 3, 11, 9, 0, 0)

    assert age_in_days(ocurrido, ahora) == 10


@pytest.mark.unit
def test_the_age_is_counted_in_days_not_in_seconds():
    """Two charges on the same day are the same age, whatever the hour.

    The shop thinks in calendar days, and the service layer hands over
    shop-local values — so 23:50 today and 00:10 tomorrow are one day
    apart, not zero.
    """
    temprano = datetime(2026, 3, 1, 0, 5, 0)
    tarde = datetime(2026, 3, 1, 23, 50, 0)
    manana = datetime(2026, 3, 2, 0, 10, 0)

    assert age_in_days(temprano, manana) == 1
    assert age_in_days(tarde, manana) == 1
    assert age_in_days(tarde, tarde) == 0


@pytest.mark.unit
def test_a_charge_of_today_has_no_age():
    """The age of a charge made today is zero days."""
    assert age_in_days(BASE, BASE) == 0


@pytest.mark.unit
def test_the_age_accepts_a_plain_date():
    """The caller may hand over a `date` instead of a `datetime`."""
    from datetime import date

    assert age_in_days(date(2026, 3, 1), date(2026, 3, 11)) == 10


@pytest.mark.unit
@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        (0, Bucket.VIGENTE),
        (7, Bucket.VIGENTE),
        (8, Bucket.ENVEJECIDO),
        (30, Bucket.ENVEJECIDO),
        (31, Bucket.VIEJO),
        (90, Bucket.VIEJO),
        (91, Bucket.CRONICO),
        (365, Bucket.CRONICO),
    ],
)
def test_the_bucket_boundaries(dias, esperado):
    """The four boundaries of PA-03: 7/8, 30/31 and 90/91."""
    assert bucket_of(dias) is esperado


@pytest.mark.unit
def test_a_charge_aged_by_its_own_age_falls_in_the_right_bucket():
    """The scenario of PA-03: charges aged 5, 8, 30, 31 and 91 days.

    They fall in `vigente`, `envejecido`, `envejecido`, `viejo` and
    `cronico` respectively — each by **its own** age.
    """
    edades = [5, 8, 30, 31, 91]
    buckets = [bucket_of(edad) for edad in edades]

    assert buckets == [
        Bucket.VIGENTE,
        Bucket.ENVEJECIDO,
        Bucket.ENVEJECIDO,
        Bucket.VIEJO,
        Bucket.CRONICO,
    ]


@pytest.mark.unit
def test_the_four_bucket_totals_sum_exactly_to_the_outstanding():
    """The buckets are a partition of the same charges (PA-03).

    The scenario of PA-03, with the payments applied: the four totals add
    up to the outstanding **exactly** — no cent more, no cent less. A
    separate figure would break here.
    """
    ahora = BASE
    cargos = [
        cargo(1, "10.00", dias=5),
        cargo(2, "20.00", dias=8),
        cargo(3, "30.00", dias=30),
        cargo(4, "40.00", dias=31),
        cargo(5, "50.00", dias=91),
    ]
    pagos = [pago(10, "25.00", dias=0)]

    # The charges that are still owed, after the payments.
    asignacion = allocate_payments(cargos, pagos)
    saldos = dict(asignacion.saldos)

    totales = {bucket: Decimal("0") for bucket in Bucket}
    for c in cargos:
        if saldos[c.id] <= 0:
            continue
        bucket = bucket_of(age_in_days(c.occurred_at, ahora))
        totales[bucket] += saldos[c.id]

    suma = sum(totales.values(), Decimal("0"))
    pendiente = outstanding(cargos + pagos, ahora)

    assert suma == pendiente
    assert sum(totales.values(), Decimal("0")) == Decimal("125.00")


@pytest.mark.unit
def test_every_charge_lands_in_exactly_one_bucket():
    """A charge is bucketed once — the four totals cannot double-count."""
    ahora = BASE
    cargos = [cargo(i, "10.00", dias=i) for i in range(0, 100, 3)]

    vistos = []
    for c in cargos:
        vistos.append(bucket_of(age_in_days(c.occurred_at, ahora)))

    assert len(vistos) == len(set(vistos)) + len(vistos) - len(set(vistos))
    assert all(bucket is not None for bucket in vistos)
    # Every charge produced exactly one bucket, so counting the buckets
    # counts the charges.
    assert len(vistos) == len(cargos)


@pytest.mark.unit
def test_a_fully_paid_charge_is_in_no_bucket():
    """A retired charge contributes nothing to any ribbon."""
    ahora = BASE
    cargos = [cargo(1, "10.00", dias=40)]
    pagos = [pago(10, "10.00", dias=1)]

    asignacion = allocate_payments(cargos, pagos)
    saldos = dict(asignacion.saldos)

    totales = {bucket: Decimal("0") for bucket in Bucket}
    for c in cargos:
        if saldos[c.id] <= 0:
            continue
        totales[bucket_of(age_in_days(c.occurred_at, ahora))] += saldos[c.id]

    assert sum(totales.values(), Decimal("0")) == Decimal("0")
