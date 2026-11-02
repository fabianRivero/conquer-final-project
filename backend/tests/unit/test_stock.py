"""The recorded movements of the shelf (CP-07).

`existencias_registradas` returns the figure **and** the qualifier
`techo_no_conteo`, and **no rule depends on the figure**.

The qualifier is the substance of this rule. The number is what the shop
logged, not a verified inventory, so it is a **ceiling** and the caller must
be told so. The test pins both halves: the arithmetic, and the fact that the
qualifier travels with the figure.

None of these tests carries the `django_db` marker: the rule reads no
database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from tienda.domain.stock import existencias_registradas
from tienda.domain.types import MovementKind, StockLine, StockQualifier

DIA = timedelta(days=1)
BASE = datetime(2026, 3, 1, 9, 0, 0)


def movimiento(
    identificador: int, kind: MovementKind, cantidad: str, dias: int = 0
) -> StockLine:
    """A `StockLine` record `dias` days after the base instant."""
    return StockLine(
        id=identificador,
        kind=kind,
        cantidad=Decimal(cantidad),
        occurred_at=BASE + dias * DIA,
    )


def entrada(identificador: int, cantidad: str, dias: int = 0) -> StockLine:
    """A stock `entrada`."""
    return movimiento(identificador, MovementKind.ENTRADA, cantidad, dias)


def salida(identificador: int, cantidad: str, dias: int = 0) -> StockLine:
    """A stock `salida`."""
    return movimiento(identificador, MovementKind.SALIDA, cantidad, dias)


@pytest.mark.unit
def test_the_figure_is_the_entries_minus_the_exits():
    """`Σ entradas − Σ salidas` (CP-07)."""
    movimientos = [
        entrada(1, "10.00"),
        entrada(2, "5.00", dias=1),
        salida(3, "3.00", dias=2),
    ]

    figura, _ = existencias_registradas(movimientos)

    assert figura == Decimal("12.00")


@pytest.mark.unit
def test_the_figure_carries_the_ceiling_qualifier():
    """The qualifier travels with the figure — it is part of the answer.

    A caller that received the number alone would read it as a count.
    """
    figura, qualifier = existencias_registradas([entrada(1, "10.00")])

    assert qualifier is StockQualifier.TECHO_NO_CONTEO
    assert qualifier == "techo_no_conteo"
    assert figura == Decimal("10.00")


@pytest.mark.unit
def test_a_product_with_no_movements_has_no_stock_and_the_qualifier():
    """Nothing was logged, so the figure is zero — and the ceiling still holds."""
    figura, qualifier = existencias_registradas([])

    assert figura == Decimal("0")
    assert qualifier is StockQualifier.TECHO_NO_CONTEO


@pytest.mark.unit
def test_the_figure_may_be_negative():
    """More was taken than was logged. The figure is not clamped."""
    figura, _ = existencias_registradas([salida(1, "5.00")])

    assert figura == Decimal("-5.00")


@pytest.mark.unit
def test_the_qualifier_is_returned_by_every_call():
    """There is no call that returns the figure without the qualifier."""
    for movimientos in (
        [],
        [entrada(1, "1.00")],
        [salida(1, "1.00")],
        [entrada(1, "1.00"), salida(2, "1.00")],
    ):
        _, qualifier = existencias_registradas(movimientos)

        assert qualifier is StockQualifier.TECHO_NO_CONTEO


@pytest.mark.unit
def test_the_rule_is_not_consulted_by_the_other_rules():
    """No rule in the package depends on the stock figure (CP-07).

    The check is an **AST** walk, not a text search: it looks for an
    actual import of the module or a call to the function, so a docstring
    that merely names the rule — as this package's `__init__.py` does — is
    not mistaken for a dependency. Only `stock.py` itself may use it.
    """
    import ast
    from pathlib import Path

    package = Path(__file__).resolve().parents[2] / "tienda" / "domain"

    for module in sorted(package.glob("*.py")):
        if module.name == "stock.py":
            continue

        arbol = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))

        for node in ast.walk(arbol):
            # An import of the sibling module.
            if isinstance(node, ast.ImportFrom) and node.module == "stock":
                pytest.fail(f"{module.name} imports the stock module")
            if isinstance(node, ast.ImportFrom) and node.module == ".stock":
                pytest.fail(f"{module.name} imports the stock module")

            # A call to the rule itself.
            if isinstance(node, ast.Call):
                nombre = node.func
                if isinstance(nombre, ast.Name) and nombre.id == "existencias_registradas":
                    pytest.fail(f"{module.name} calls existencias_registradas")
                if (
                    isinstance(nombre, ast.Attribute)
                    and nombre.attr == "existencias_registradas"
                ):
                    pytest.fail(f"{module.name} calls existencias_registradas")
