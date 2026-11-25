"""The Slice 10.5, T2: **the person accepts or rejects the fiado**.

**The shop asks; she answers.** The owner prepares a `FiadoPropuesto`
and it waits for HER - not for the owner, and not for the `dependiente`.
Her account is where the answer is given, and the answer is hers.

**The acceptance writes the charge.** The same four rows the staff's
confirmation wrote: the `LedgerEntry(cargo)`, the `CargoLinea[]` copied

from the proposal's own lines, the `Confirmacion(confirmado)` and the
proposal's `confirmed_at`. If any of them fails, none of them survives.

**The rejection writes the instant and her reason.** No charge, no lines,
no confirmation: the outstanding never moved, because it never moved in
the first place.

**The reason is free text and it may be empty.** A refusal without an
explanation is not an answer, and an empty explanation is still an
answer: she is not obliged to justify herself to the shop.

**The shop may NOT answer for her.** The owner's route refuses: the
answer is the person's, and a shop that could accept for her would be a
shop that could decide for her.
"""

from __future__ import annotations

from tests.integration.personas import crear_persona

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
    LedgerEntry,
    PerfilCliente,
    Producto,
    PropuestaLinea,
    Shop,
    Vinculo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dueno(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def tienda(db):
    return Shop.objects.create(
        name="Tienda", opening_cash=Decimal("150.00"), currency="EUR"
    )


@pytest.fixture
def cliente(tienda, dueno):
    """The person, her account, and the LINK that says she is trusted."""

    _usuario, fila = crear_persona("ana", alias="Ana", dueno=dueno)
    Vinculo.objects.create(
        tienda=tienda,
        cliente=fila,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    return fila


@pytest.fixture
def persona(db, cliente):
    """**Her own account**, with her client profile."""
    user = User.objects.create_user(
        username="ana.perez", password="secreta123"
    )
    PerfilCliente.objects.create(user=user)
    cliente.user = user
    cliente.save(update_fields=["user"])
    return user


@pytest.fixture
def producto(tienda):
    return Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )


@pytest.fixture
def api_persona(persona):
    """The client of the person's own account - a session, no `shop_id`."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(persona)
    sesion = SessionStore()
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


@pytest.fixture
def api_dueno(dueno, tienda):
    """The owner's client, with the shop in its session."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(dueno)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


@pytest.fixture
def propuesta(tienda, cliente, dueno, producto):
    """A prepared fiado, waiting for her answer."""
    fila = FiadoPropuesto.objects.create(
        shop=tienda,
        customer=cliente,
        user=dueno,
        estado="pendiente",
        total=Decimal("8.00"),
        created_at=timezone.now(),
    )
    PropuestaLinea.objects.create(
        propuesta=fila,
        producto=producto,
        cantidad=Decimal("1"),
        precio_unitario=Decimal("8.00"),
        total=Decimal("8.00"),
    )
    return fila


# ---------------------------------------------------------------------------
# She accepts
# ---------------------------------------------------------------------------


def test_she_accepts_the_fiado_from_her_own_account(
    api_persona, persona, propuesta, cliente, tienda
):
    """**The shop asked; she answers, from her own account.**

    The answer writes the charge: the `LedgerEntry(cargo)`, the
    `CargoLinea[]` copied from the proposal's own lines, the
    `Confirmacion(confirmado)` and the proposal's `confirmed_at`.
    """
    respuesta = api_persona.post(
        reverse("api:cuenta_fiado_aceptar"),
        {"fiado_id": propuesta.id},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.content

    propuesta.refresh_from_db()
    assert propuesta.estado == "aceptado"
    assert propuesta.confirmed_at is not None

    # The charge exists, and it is the proposal's own figure.
    cargo = LedgerEntry.objects.get(kind="cargo")
    assert cargo.customer_id == cliente.id
    assert cargo.shop_id == tienda.id
    assert cargo.amount == Decimal("8.00")

    # Its lines are COPIED from the proposal's own lines.
    lineas = list(CargoLinea.objects.filter(cargo=cargo))
    assert len(lineas) == 1
    assert lineas[0].producto_id == propuesta.lineas.get().producto_id
    assert lineas[0].total == Decimal("8.00")

    # And it carries the confirmation.
    confirmacion = Confirmacion.objects.get(cargo=cargo)
    assert confirmacion.estado == "confirmado"


def test_the_charge_is_written_by_the_server_and_not_by_her(
    api_persona, persona, propuesta, cliente
):
    """**She does not write the charge.** She says yes, and the server
    writes the four rows.

    A body that carries the charge's own fields is refused: the figure
    is the shop's, and the shop's figure is what the proposal already
    holds.
    """
    respuesta = api_persona.post(
        reverse("api:cuenta_fiado_aceptar"),
        {"fiado_id": propuesta.id, "importe": "99.00"},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"


def test_she_cannot_accept_the_same_fiado_twice(
    api_persona, persona, propuesta
):
    """The move is one-way: an accepted fiado is not accepted again."""
    primera = api_persona.post(
        reverse("api:cuenta_fiado_aceptar"),
        {"fiado_id": propuesta.id},
        format="json",
    )
    assert primera.status_code == 200, primera.content

    segunda = api_persona.post(
        reverse("api:cuenta_fiado_aceptar"),
        {"fiado_id": propuesta.id},
        format="json",
    )

    assert segunda.status_code == 422, segunda.content
    assert segunda.json()["codigo_error"] == "propuesta_ya_aceptada"
    assert LedgerEntry.objects.filter(kind="cargo").count() == 1


# ---------------------------------------------------------------------------
# She rejects
# ---------------------------------------------------------------------------


def test_she_rejects_the_fiado_with_a_reason(
    api_persona, persona, propuesta, cliente
):
    """**The reason is hers**, and it is free text.

    The rejection writes the instant and her reason, and **nothing
    else**: no charge, no lines, no confirmation. The outstanding never
    moved, because it never moved in the first place.
    """
    respuesta = api_persona.post(
        reverse("api:cuenta_fiado_rechazar"),
        {"fiado_id": propuesta.id, "motivo": "Ahora no puedo."},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.content

    propuesta.refresh_from_db()
    assert propuesta.estado == "rechazado"
    assert propuesta.canceled_at is not None
    assert propuesta.motivo_rechazo == "Ahora no puedo."

    # And the book is untouched.
    assert LedgerEntry.objects.filter(kind="cargo").count() == 0
    assert CargoLinea.objects.count() == 0
    assert Confirmacion.objects.count() == 0


def test_the_reason_may_be_empty(
    api_persona, persona, propuesta
):
    """**An empty reason is still an answer.**

    She is not obliged to justify herself to the shop: the refusal is
    hers and it needs no explanation.
    """
    respuesta = api_persona.post(
        reverse("api:cuenta_fiado_rechazar"),
        {"fiado_id": propuesta.id},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.content
    propuesta.refresh_from_db()
    assert propuesta.estado == "rechazado"
    assert not propuesta.motivo_rechazo


def test_she_cannot_reject_a_fiado_that_is_not_hers(
    api_persona, persona, tienda, dueno, producto
):
    """**The fiado of another person is NOT FOUND.**

    Not refused - **not found**. A 403 would confirm that it exists,
    and the person has no business learning that somebody else is being
    asked.
    """
    otra_usuario, otra = crear_persona("beto", alias="Beto")
    ajena = FiadoPropuesto.objects.create(
        shop=tienda,
        customer=otra,
        user=dueno,
        estado="pendiente",
        total=Decimal("3.00"),
        created_at=timezone.now(),
    )

    respuesta = api_persona.post(
        reverse("api:cuenta_fiado_rechazar"),
        {"fiado_id": ajena.id},
        format="json",
    )

    assert respuesta.status_code == 404, respuesta.content
    ajena.refresh_from_db()
    assert ajena.estado == "pendiente"


# ---------------------------------------------------------------------------
# The shop may NOT answer for her
# ---------------------------------------------------------------------------


def test_the_shop_cannot_accept_the_fiado_for_her(
    api_dueno, dueno, tienda, propuesta
):
    """**The answer is hers.** The owner's route refuses.

    A shop that could accept for her would be a shop that could decide
    for her, and the whole consent of the 10.3 would be worth nothing.
    """
    from tienda.api.permissions import current_shop

    # The owner's session carries the shop, so the route sees a staff
    # session - and the person's routes refuse it.
    from django.contrib.sessions.backends.db import SessionStore

    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api_dueno.cookies["sessionid"] = sesion.session_key

    respuesta = api_dueno.post(
        reverse("api:cuenta_fiado_aceptar"),
        {"fiado_id": propuesta.id},
        format="json",
    )

    assert respuesta.status_code in (403, 404), respuesta.content
    propuesta.refresh_from_db()
    assert propuesta.estado == "pendiente"
    assert LedgerEntry.objects.filter(kind="cargo").count() == 0
