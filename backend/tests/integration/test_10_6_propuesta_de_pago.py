"""The Slice 10.6, T2: **she proposes the payment from her account**.

**The shop is NAMED, and it is not a guess.** A person may owe in
SEVERAL shops, and a payment belongs to ONE of them: the `pago` is
appended to that shop's book, and the FIFO retires that shop's charges.

**Before this, the service picked the FIRST accepted link.** That was a
guess - and a guess that pays the wrong shop's debt: a person owing 30
in one shop and 20 in another could see her payment land in either one.

**And the proposal names no charge.** The person does not choose which
debt it pays: she proposes an amount and the FIFO decides which charges
it retires (ADR-27). A body that carries a `cargo_id` is refused on the
**presence** of the field.

**It writes NO ledger row.** The `pago` is a separate entry that the
owner appends when he validates the proposal.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from tests.integration.personas import crear_persona

from tienda.models import (
    CargoLinea,
    Confirmacion,
    FiadoPropuesto,
    LedgerEntry,
    PagoPropuesto,
    Producto,
    Vinculo,
)


@pytest.fixture
def dueno(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def tienda(db):
    from tienda.models import Shop

    return Shop.objects.create(
        name="Tienda", opening_cash=Decimal("150.00"), currency="EUR"
    )


@pytest.fixture
def otra_tienda(db):
    from tienda.models import Shop

    return Shop.objects.create(
        name="Otra", opening_cash=Decimal("0.00"), currency="EUR"
    )


@pytest.fixture
def persona(db, tienda, otra_tienda, dueno):
    """**She owes in TWO shops.** That is the whole point of the test."""
    usuario, cliente = crear_persona("ana", alias="Ana")
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    Vinculo.objects.create(
        tienda=otra_tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("30.00"),
    )
    return usuario, cliente


@pytest.fixture
def api_persona(persona):
    """The client of the person's own account."""
    from django.contrib.sessions.backends.db import SessionStore

    usuario, _cliente = persona

    api = APIClient()
    api.force_authenticate(usuario)
    sesion = SessionStore()
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


def _cargo(tienda, cliente, dueno, producto, *, importe="8.00"):
    cargo = LedgerEntry.objects.create(
        shop=tienda,
        customer=cliente,
        user=dueno,
        kind="cargo",
        amount=Decimal(importe),
        occurred_at=timezone.now(),
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
        confirmado_en=timezone.now(),
        origen="tienda",
        confirmado_por=dueno,
    )
    return cargo


# ---------------------------------------------------------------------------
# The proposal
# ---------------------------------------------------------------------------


def test_the_proposal_writes_no_ledger_row(
    api_persona, persona, tienda, dueno
):
    """**The proposal writes NOTHING to the book.**

    The `pago` is a separate `LedgerEntry` that the owner appends when
    he validates it, so the book stays append-only even though the
    request that preceded it is not.
    """
    respuesta = api_persona.post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00", "referencia": "billete", "tienda_id": tienda.id},
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.content

    propuesta = PagoPropuesto.objects.get()
    assert propuesta.estado == "pendiente"
    assert propuesta.importe == Decimal("5.00")
    assert propuesta.shop_id == tienda.id

    assert LedgerEntry.objects.count() == 0
    assert CargoLinea.objects.count() == 0


def test_the_proposal_names_the_shop_it_is_for(
    api_persona, persona, tienda, otra_tienda, dueno
):
    """**The shop goes in the proposal, not a guess.**

    She owes in two shops, and the payment goes to the one she names.
    """
    respuesta = api_persona.post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00", "tienda_id": otra_tienda.id},
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.content

    propuesta = PagoPropuesto.objects.get()
    assert propuesta.shop_id == otra_tienda.id


def test_a_proposal_without_a_shop_is_refused_when_she_owes_in_several(
    api_persona, persona, tienda, otra_tienda, dueno
):
    """**Guessing would pay the wrong shop's debt.**

    When she owes in ONE shop the proposal may go there; when she owes
    in several, the refusal says which shop it is for.
    """
    respuesta = api_persona.post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00"},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "tienda_requerida"
    assert PagoPropuesto.objects.count() == 0


def test_a_proposal_without_a_shop_goes_to_the_only_shop_she_owes_in(
    api_persona, persona, tienda, dueno
):
    """**When there is only one, there is no doubt.**"""
    Vinculo.objects.filter(cliente=persona[1]).exclude(
        tienda=tienda
    ).delete()

    respuesta = api_persona.post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00"},
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.content
    assert PagoPropuesto.objects.get().shop_id == tienda.id


def test_the_proposal_names_no_charge(api_persona, persona, tienda, dueno):
    """**The proposal does not choose which debt it pays.**

    It proposes an amount and the FIFO decides (ADR-27). A body that
    carries a `cargo_id` is refused on the PRESENCE of the field.
    """
    producto = Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("8.00"), unidad="unidad"
    )
    cargo = _cargo(tienda, persona[1], dueno, producto)

    respuesta = api_persona.post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00", "tienda_id": tienda.id, "cargo_id": cargo.id},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"
    assert PagoPropuesto.objects.count() == 0


def test_a_non_positive_amount_is_refused(api_persona, persona, tienda, dueno):
    """Rule 17: the amount must be greater than zero."""
    respuesta = api_persona.post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "0.00", "tienda_id": tienda.id},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "importe_no_positivo"


def test_a_shop_she_does_not_owe_in_is_refused(
    api_persona, persona, tienda, dueno
):
    """**She cannot pay a shop she does not owe to.**

    The scope is the PERSON's, and the shop has to be one of hers.
    """
    ajena = Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("8.00"), unidad="unidad"
    )
    from tienda.models import Shop

    otra = Shop.objects.create(
        name="Ajena", opening_cash=Decimal("0.00"), currency="EUR"
    )

    respuesta = api_persona.post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00", "tienda_id": otra.id},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "tienda_requerida"
    assert PagoPropuesto.objects.count() == 0


def test_the_shop_cannot_propose_for_her(api_persona, persona, tienda, dueno):
    """**The staff session does not reach the person's routes.**

    The proposal is HERS: a shop that could propose for her would be a
    shop that could pay her debt with her own money.
    """
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(dueno)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    respuesta = api.post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00", "tienda_id": tienda.id},
        format="json",
    )

    assert respuesta.status_code in (403, 404), respuesta.content
    assert PagoPropuesto.objects.count() == 0
