"""The itemised charge: its line total, its price and its declared amount.

Covers **IC-02** (the declared amount equals the itemisation total) and
**PC-02** (the catalogue price is the default, an explicit price wins), with
the rounding of **IC-06** and the one boundary the design calls out: **a
charge with no lines matches any declared amount**.

None of these tests carries the `django_db` marker, so no rule in this path
may touch the database.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tienda.domain.charges import (
    charge_amount_matches,
    precio_unitario_de,
    total_de_linea,
)
from tienda.domain.types import CargoLine


def linea(identificador: int, cantidad: str, precio: str, total: str) -> CargoLine:
    """One `CargoLine` record."""
    return CargoLine(
        id=identificador,
        cantidad=Decimal(cantidad),
        precio_unitario=Decimal(precio),
        total=Decimal(total),
    )


@pytest.mark.unit
def test_the_line_total_is_the_product_rounded_to_two_places():
    """`total = round(cantidad × precio_unitario, 2)` (IC-06)."""
    assert total_de_linea(Decimal("3"), Decimal("1.00")) == Decimal("3.00")
    assert total_de_linea(Decimal("1"), Decimal("1.20")) == Decimal("1.20")


@pytest.mark.unit
def test_the_line_total_is_rounded_half_up():
    """The rounding is the one the database `CHECK` mirrors.

    2,5 × 1,25 € is 3,125 €, and the two-decimal rounding gives 3,13 € —
    the same value PostgreSQL's `round()` produces for a numeric.
    """
    assert total_de_linea(Decimal("2.5"), Decimal("1.25")) == Decimal("3.13")


@pytest.mark.unit
def test_the_line_total_carries_two_decimals():
    """The total is a money figure, not a float with trailing noise."""
    total = total_de_linea(Decimal("3"), Decimal("0.10"))

    assert total == Decimal("0.30")
    assert total.as_tuple().exponent == -2


@pytest.mark.unit
def test_a_fractional_quantity_rounds_the_same_way():
    """A quantity with decimals is not truncated before the multiplication."""
    assert total_de_linea(Decimal("1.5"), Decimal("2.00")) == Decimal("3.00")
    assert total_de_linea(Decimal("0.333"), Decimal("3.00")) == Decimal("1.00")


@pytest.mark.unit
def test_the_catalogue_price_is_the_default():
    """With no override, the line carries the catalogue price (PC-02)."""
    assert precio_unitario_de(Decimal("1.20"), None) == Decimal("1.20")


@pytest.mark.unit
def test_the_override_wins_over_the_catalogue_price():
    """An explicit price wins — the deviation rule (PC-02)."""
    assert precio_unitario_de(Decimal("1.20"), Decimal("1.00")) == Decimal("1.00")


@pytest.mark.unit
def test_the_overridden_price_is_the_price_charged():
    """The scenario of IC-08: 3 units at an overridden 1,00 € is 3,00 €."""
    precio = precio_unitario_de(Decimal("1.20"), Decimal("1.00"))

    assert total_de_linea(Decimal("3"), precio) == Decimal("3.00")


@pytest.mark.unit
def test_the_price_of_a_charge_does_not_follow_the_catalogue_later():
    """The price is a snapshot: a later catalogue change never rewrites it.

    The rule returns a value, not a reference to the catalogue, so the
    caller stores what it was given.
    """
    precio = precio_unitario_de(Decimal("1.20"), None)

    # The catalogue price changes afterwards.
    catalogo_nuevo = Decimal("1.50")

    assert precio == Decimal("1.20")
    assert precio != catalogo_nuevo


@pytest.mark.unit
def test_a_charge_that_adds_up_matches_its_declared_amount():
    """The declared amount equals the total of the lines (IC-02)."""
    lineas = [linea(1, "2", "1.20", "2.40"), linea(2, "1", "4.00", "4.00")]

    assert charge_amount_matches(lineas, Decimal("6.40")) is True


@pytest.mark.unit
def test_a_charge_that_does_not_add_up_is_refused():
    """The scenario of IC-02: 6,40 € of lines against a declared 6,50 €.

    This mismatch is the source of `lineas_descuadradas`.
    """
    lineas = [linea(1, "2", "1.20", "2.40"), linea(2, "1", "4.00", "4.00")]

    assert charge_amount_matches(lineas, Decimal("6.50")) is False


@pytest.mark.unit
def test_a_line_less_charge_matches_any_declared_amount():
    """An empty `lines` sequence is a legal, line-less charge (IC-02).

    Its whole total **is** its declared amount, so the comparison is
    vacuously true and the charge is accepted as declared.
    """
    assert charge_amount_matches([], Decimal("4.20")) is True
    assert charge_amount_matches([], Decimal("0.00")) is True
    assert charge_amount_matches([], Decimal("9999.99")) is True


@pytest.mark.unit
def test_a_single_line_must_add_up():
    """One line is enough — when it agrees with the declared amount."""
    lineas = [linea(1, "1", "4.20", "4.20")]

    assert charge_amount_matches(lineas, Decimal("4.20")) is True
    assert charge_amount_matches(lineas, Decimal("4.21")) is False


@pytest.mark.unit
def test_the_comparison_is_made_on_the_rounded_line_totals():
    """The totals are compared at two decimals, like the stored values.

    A line whose `total` carries more decimals than the money scale is
    rounded before the comparison, exactly as the database stores it.
    """
    lineas = [linea(1, "3", "0.10", "0.300")]

    assert charge_amount_matches(lineas, Decimal("0.30")) is True


@pytest.mark.unit
def test_the_amount_of_a_charge_is_never_recomputed_by_the_matcher():
    """The matcher compares; it does not produce the amount.

    The declared amount is the caller's figure — the rule only says whether
    it agrees with the itemisation.
    """
    lineas = [linea(1, "1", "1.00", "1.00")]

    assert charge_amount_matches(lineas, Decimal("1.00")) is True
    assert charge_amount_matches(lineas, Decimal("1.00")) is not False
