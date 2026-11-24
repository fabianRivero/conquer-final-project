"""The Slice 10.5, T3: **her own account** carries the figures.

**A pending link shows the shop's name and the buttons - and nothing
else.** If she could see the debt and the ageing first, the consent
would be a formality: she would already have seen everything the
acceptance reveals. That rule does not move.

**An ACCEPTED link opens the figures.** And the figures are hers to
read: how much she owes **in that shop**, how old the oldest debt is,
and the fiados with their state.

**The figures are PER SHOP.** "She owes 30 here" and "she owes 20
there" are two facts, and one account that mixed them would be lying
about both. The limit and the ageing belong to the link, and the link
names the shop.

**The state of a charge is a WORD**: `pendiente`, `parcial`, `pagado`.
It is derived on read and never stored - a `pagado` column on the
charge would break the append-only guarantee of the book (ADR-27).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from tienda.models import (
    CargoLinea,
    Confirmacion,
    Customer,
    FiadoPropuesto,
    ImputacionPago,
    LedgerEntry,
    PerfilCliente,
    Producto,
    PropuestaLinea,
    Shop,
    Vinculo,
)


@pytest.fixture
def dueno(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def tienda(db):
    return Shop.objects.create(
        name="Tienda", opening_cash=Decimal("150.00"), currency="EUR"
    )


@pytest.fixture
def otra_tienda(db):
    return Shop.objects.create(
        name="Otra", opening_cash=Decimal("0.00"), currency="EUR"
    )


@pytest.fixture
def cliente(tienda, otra_tienda, dueno):
    """A person trusted in TWO shops, with a DIFFERENT limit in each."""
    fila = Customer.objects.create(alias="Ana", created_by=dueno)
    Vinculo.objects.create(
        tienda=tienda,
        cliente=fila,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    Vinculo.objects.create(
        tienda=otra_tienda,
        cliente=fila,
        estado="aceptado",
        credit_limit=Decimal("30.00"),
    )
    return fila


@pytest.fixture
def persona(db, cliente):
    user = User.objects.create_user(
        username="ana.perez", password="secreta123"
    )
    PerfilCliente.objects.create(user=user)
    cliente.user = user
    cliente.save(update_fields=["user"])
    return user


@pytest.fixture
def api_persona(persona):
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(persona)
    sesion = SessionStore()
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


@pytest.fixture
def producto(tienda):
    return Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )


def _cargo(tienda, cliente, dueno, producto, *, importe="8.00", dias=0):
    momento = timezone.now() - timezone.timedelta(days=dias)
    cargo = LedgerEntry.objects.create(
        shop=tienda,
        customer=cliente,
        user=dueno,
        kind="cargo",
        amount=Decimal(importe),
        occurred_at=momento,
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
        confirmado_en=momento,
        origen="tienda",
        confirmado_por=dueno,
    )
    return cargo


# ---------------------------------------------------------------------------
# The figures of an accepted link
# ---------------------------------------------------------------------------


def test_the_account_carries_the_amount_of_each_shop(
    api_persona, persona, cliente, tienda, otra_tienda, dueno
):
    """**The amounts are PER SHOP.** One account that mixed them would be
    lying about both.
    """
    producto = Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )
    otro = Producto.objects.create(
        shop=otra_tienda, nombre="Leche", precio=Decimal("1.00"), unidad="unidad"
    )
    _cargo(tienda, cliente, dueno, producto, importe="30.00")
    _cargo(otra_tienda, cliente, dueno, otro, importe="20.00")

    respuesta = api_persona.get(reverse("api:cuenta_vinculos"))

    assert respuesta.status_code == 200, respuesta.content
    filas = {f["tienda"]: f for f in respuesta.json()}
    assert filas["Tienda"]["pendiente"] == Decimal("30.00")
    assert filas["Otra"]["pendiente"] == Decimal("20.00")


def test_the_account_carries_the_antiguedad_of_each_shop(
    api_persona, persona, cliente, tienda, otra_tienda, dueno
):
    """**The ageing is per shop too.**

    "In THIS shop she has not paid for 90 days" says something. "Ana has
    not paid for 90 days" says nothing.
    """
    producto = Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )
    otro = Producto.objects.create(
        shop=otra_tienda, nombre="Leche", precio=Decimal("1.00"), unidad="unidad"
    )
    _cargo(tienda, cliente, dueno, producto, importe="30.00", dias=100)
    _cargo(otra_tienda, cliente, dueno, otro, importe="20.00", dias=5)

    respuesta = api_persona.get(reverse("api:cuenta_vinculos"))

    filas = {f["tienda"]: f for f in respuesta.json()}
    assert filas["Tienda"]["antiguedad_max_dias"] == 100
    assert filas["Otra"]["antiguedad_max_dias"] == 5


def test_the_account_carries_the_limit_of_each_shop(
    api_persona, persona, cliente, tienda, otra_tienda
):
    """The limit is the LINK's, and the link names the shop."""
    respuesta = api_persona.get(reverse("api:cuenta_vinculos"))

    filas = {f["tienda"]: f for f in respuesta.json()}
    assert filas["Tienda"]["credit_limit"] == Decimal("100.00")
    assert filas["Otra"]["credit_limit"] == Decimal("30.00")


# ---------------------------------------------------------------------------
# The fiados and their state
# ---------------------------------------------------------------------------


def test_the_account_carries_the_fiados_with_their_state(
    api_persona, persona, cliente, tienda, dueno, producto
):
    """**Her fiados, with their state**: `pendiente`, `aceptado` and
    `rechazado`.

    The rejected one carries **the reason she gave**, because a refusal
    without an explanation is not an answer - and she is the one who gave
    it.
    """
    pendiente = FiadoPropuesto.objects.create(
        shop=tienda,
        customer=cliente,
        user=dueno,
        estado="pendiente",
        total=Decimal("5.00"),
        created_at=timezone.now(),
    )
    PropuestaLinea.objects.create(
        propuesta=pendiente,
        producto=producto,
        cantidad=Decimal("1"),
        precio_unitario=Decimal("5.00"),
        total=Decimal("5.00"),
    )

    rechazado = FiadoPropuesto.objects.create(
        shop=tienda,
        customer=cliente,
        user=dueno,
        estado="rechazado",
        total=Decimal("7.00"),
        created_at=timezone.now(),
        canceled_at=timezone.now(),
        motivo_rechazo="Ahora no puedo.",
    )

    respuesta = api_persona.get(reverse("api:cuenta_fiados"))

    assert respuesta.status_code == 200, respuesta.content
    filas = {f["id"]: f for f in respuesta.json()}

    assert filas[pendiente.id]["estado"] == "pendiente"
    assert filas[pendiente.id]["total"] == Decimal("5.00")

    assert filas[rechazado.id]["estado"] == "rechazado"
    assert filas[rechazado.id]["motivo"] == "Ahora no puedo."


def test_a_pending_fiado_carries_its_lines_and_its_total(
    api_persona, persona, cliente, tienda, dueno, producto
):
    """**A figure she cannot see broken down is not a figure she
    confirmed.** The lines are there before she answers.
    """
    pendiente = FiadoPropuesto.objects.create(
        shop=tienda,
        customer=cliente,
        user=dueno,
        estado="pendiente",
        total=Decimal("5.00"),
        created_at=timezone.now(),
    )
    PropuestaLinea.objects.create(
        propuesta=pendiente,
        producto=producto,
        cantidad=Decimal("2"),
        precio_unitario=Decimal("2.50"),
        total=Decimal("5.00"),
    )

    respuesta = api_persona.get(reverse("api:cuenta_fiados"))

    filas = {f["id"]: f for f in respuesta.json()}
    lineas = filas[pendiente.id]["lineas"]
    assert len(lineas) == 1
    assert lineas[0]["producto"] == "Pan"
    assert lineas[0]["cantidad"] == Decimal("2")
    assert lineas[0]["total"] == Decimal("5.00")


def test_the_charges_carry_their_state_including_the_partial_one(
    api_persona, persona, cliente, tienda, dueno, producto
):
    """**The state of a charge is a word**, and `parcial` is one of them.

    It is derived on read: the amount paid comes from the
    `ImputacionPago` rows, and a stored balance would break the
    append-only guarantee of the book.
    """
    cargo = _cargo(tienda, cliente, dueno, producto, importe="8.00")

    pago = LedgerEntry.objects.create(
        shop=tienda,
        customer=cliente,
        user=dueno,
        kind="pago",
        amount=Decimal("3.00"),
        occurred_at=timezone.now(),
    )
    ImputacionPago.objects.create(
        pago=pago, cargo=cargo, importe=Decimal("3.00")
    )

    respuesta = api_persona.get(reverse("api:cuenta_cargos"))

    assert respuesta.status_code == 200, respuesta.content
    filas = {f["id"]: f for f in respuesta.json()}
    assert filas[cargo.id]["estado"] == "parcial"
    assert filas[cargo.id]["saldo"] == Decimal("5.00")


def test_a_charge_that_was_paid_in_full_is_pagado(
    api_persona, persona, cliente, tienda, dueno, producto
):
    """The charge that was paid is `pagado`."""
    cargo = _cargo(tienda, cliente, dueno, producto, importe="8.00")

    pago = LedgerEntry.objects.create(
        shop=tienda,
        customer=cliente,
        user=dueno,
        kind="pago",
        amount=Decimal("8.00"),
        occurred_at=timezone.now(),
    )
    ImputacionPago.objects.create(
        pago=pago, cargo=cargo, importe=Decimal("8.00")
    )

    respuesta = api_persona.get(reverse("api:cuenta_cargos"))

    filas = {f["id"]: f for f in respuesta.json()}
    assert filas[cargo.id]["estado"] == "pagado"
    assert filas[cargo.id]["saldo"] == Decimal("0.00")


# ---------------------------------------------------------------------------
# The consent rule does not move
# ---------------------------------------------------------------------------


def test_a_pending_link_still_shows_only_the_shop_and_the_buttons(
    api_persona, persona, cliente, tienda, dueno
):
    """**The rule of the 10.3 does not move.**

    A pending link shows the shop's name and nothing else: if she could
    see the debt and the ageing first, the consent would be a formality.
    """
    Vinculo.objects.filter(cliente=cliente, tienda=tienda).update(
        estado="pendiente"
    )

    respuesta = api_persona.get(reverse("api:cuenta_vinculos"))

    filas = {f["tienda"]: f for f in respuesta.json()}
    fila = filas["Tienda"]
    assert "credit_limit" not in fila
    assert "pendiente" not in fila
    assert "antiguedad_max_dias" not in fila
