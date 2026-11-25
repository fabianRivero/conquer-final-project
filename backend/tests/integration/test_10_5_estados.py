"""The Slice 10.5, T1: the states of the `FiadoPropuesto`.

**The person decides.** Until now the proposal moved from `pendiente` to
`confirmado` or `cancelado`, and the words said who acted: the shop
confirmed, the shop cancelled. The client never wrote to the book.

**Now the words say what the person DID**: `aceptado` and `rechazado`.
The shop ASKED; she ANSWERED. And the rejection carries a **reason** -
free text, and it may be empty: a refusal without an explanation is
not an answer, and an empty one is still an answer.

**The `Confirmacion.estado` is a DIFFERENT thing and does not move.**
It is the state of the CHARGE - and it has one value only,
`confirmado`. The charge that exists because she accepted is
`confirmado`; the proposal she accepted is `aceptado`. Two rows, two
vocabularies, two questions.

**The `parcial` is the state of a charge that is partly paid.** It is
derived on read - never stored: the amount paid comes from the
`ImputacionPago` rows, and a stored balance would break the
append-only guarantee of the book (ADR-27).
"""

from __future__ import annotations

from tests.integration.personas import crear_persona


from decimal import Decimal

import pytest

from django.contrib.auth.models import User

from tienda.models import (
    CargoLinea,
    Confirmacion,
    Customer,
    ImputacionPago,
    LedgerEntry,
    Producto,
    Shop,
    Vinculo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def tienda(db):
    return Shop.objects.create(
        name="Tienda", opening_cash=Decimal("150.00"), currency="EUR"
    )


@pytest.fixture
def customer(tienda, owner):
    cliente_usuario, cliente = crear_persona("ana", alias="Ana")
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    return cliente


@pytest.fixture
def producto(tienda):
    return Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )


def _cargo(tienda, customer, owner, producto, *, importe="8.00"):
    cargo = LedgerEntry.objects.create(
        shop=tienda,
        customer=customer,
        user=owner,
        kind="cargo",
        amount=Decimal(importe),
        occurred_at=timezone_now(),
    )
    CargoLinea.objects.create(
        cargo=cargo,
        producto=producto,
        cantidad=Decimal("1"),
        precio_unitario=Decimal(importe),
        total=Decimal(importe),
    )
    Confirmacion.objects.create(
        cargo=cargo,
        estado="confirmado",
        confirmado_en=timezone_now(),
        origen="tienda",
        confirmado_por=owner,
    )
    return cargo


def timezone_now():
    from django.utils import timezone

    return timezone.now()


# ---------------------------------------------------------------------------
# The proposal's vocabulary
# ---------------------------------------------------------------------------


def test_the_proposal_vocabulary_is_the_persons_answer(db):
    """`pendiente`, `aceptado`, `rechazado`.

    The old vocabulary - `confirmado` and `cancelado` - said the SHOP
    acted. The new one says what the PERSON did.
    """
    from tienda.models import PROPUESTA_ESTADOS

    assert PROPUESTA_ESTADOS == ("pendiente", "aceptado", "rechazado")


def test_the_confirmation_vocabulary_does_not_move(db):
    """**The `Confirmacion` is a different thing and it does not move.**

    It is the state of the CHARGE, and it has one value only: the
    charge that exists because she accepted is `confirmado`. The
    proposal she accepted is `aceptado`.

    Two rows, two vocabularies, two questions - and the test that says
    so is this one.
    """
    from tienda.models import CONFIRMATION_STATES

    assert CONFIRMATION_STATES == ("confirmado",)


def test_the_rejection_carries_a_reason_and_it_may_be_empty(db):
    """**The reason is free text and it may be empty.**

    A refusal without an explanation is not an answer, and an empty
    explanation is still an answer.
    """
    from tienda.models import FiadoPropuesto

    campo = FiadoPropuesto._meta.get_field("motivo_rechazo")

    assert campo.blank is True
    assert campo.null is True


def test_the_rejection_reason_is_readable_by_the_shop(db):
    """The shop reads the reason. It is the shop's own column."""
    from tienda.models import FiadoPropuesto

    campo = FiadoPropuesto._meta.get_field("motivo_rechazo")

    assert campo.get_internal_type() == "TextField"


# ---------------------------------------------------------------------------
# The state of a charge
# ---------------------------------------------------------------------------


def test_a_charge_that_was_not_paid_is_pendiente(
    db, tienda, customer, owner, producto
):
    """The charge nobody paid is `pendiente`."""
    from tienda import services

    cargo = _cargo(tienda, customer, owner, producto)

    assert services.estado_cargo(cargo) == "pendiente"


def test_a_charge_that_was_paid_in_full_is_pagado(
    db, tienda, customer, owner, producto
):
    """The charge that was paid is `pagado`."""
    from tienda import services

    cargo = _cargo(tienda, customer, owner, producto, importe="8.00")

    pago = LedgerEntry.objects.create(
        shop=cargo.shop,
        customer=cargo.customer,
        user=User.objects.get(username="dueno"),
        kind="pago",
        amount=Decimal("8.00"),
        occurred_at=timezone_now(),
    )
    ImputacionPago.objects.create(
        pago=pago, cargo=cargo, importe=Decimal("8.00")
    )

    assert services.estado_cargo(cargo) == "pagado"


def test_a_charge_that_was_partly_paid_is_parcial(
    db, tienda, customer, owner, producto
):
    """**The `parcial` exists**: the payment that retires part of a
    charge.

    It is DERIVED on read and never stored: a `pagado` column on the
    charge would break the append-only guarantee of the book.
    """
    from tienda import services

    cargo = _cargo(tienda, customer, owner, producto, importe="8.00")

    pago = LedgerEntry.objects.create(
        shop=cargo.shop,
        customer=cargo.customer,
        user=User.objects.get(username="dueno"),
        kind="pago",
        amount=Decimal("3.00"),
        occurred_at=timezone_now(),
    )
    ImputacionPago.objects.create(
        pago=pago, cargo=cargo, importe=Decimal("3.00")
    )

    assert services.saldo_de(cargo) == Decimal("5.00")
    assert services.estado_cargo(cargo) == "parcial"
