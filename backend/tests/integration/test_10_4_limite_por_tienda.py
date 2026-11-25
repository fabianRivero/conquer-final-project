"""The Slice 10.4: the owner's policy is PER SHOP, and the route that
writes it has to work.

**The bug this file pins.** `ClienteDetalleView.patch` read `shop_id`
and never assigned it: the variable lived in `get`, and `patch` is a
different method. So the ONE route that sets the `credit_limit` -
`PATCH /api/v1/clientes/{id}/` - raised `NameError` and answered 500.

It was never caught because the suite had no test that PATCHED the
limit. The GET was walked by the leak tests; the PATCH was not walked
by anybody.

**Why the limit is the LINK's.** The trust is the owner's AND it is of
that shop: Ana may have 100 in one and 30 in another. So the PATCH
writes the LINK's limit, and only that link's.
"""

from __future__ import annotations

from tests.integration.personas import crear_persona


from decimal import Decimal

import pytest

from tests.conftest import membresia

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from tienda.models import (
    Customer,
    PerfilTienda,
    Shop,
    Vinculo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner(db, negocio):
    membresia(negocio, negocio.user, "dueno")
    return negocio.user


@pytest.fixture
def tienda(db, negocio):
    return negocio.shop


@pytest.fixture
def otra_tienda(db):
    """A second shop, with its own owner and its own business."""
    dueno = User.objects.create_user(username="dueno2", password="secreta123")
    perfil = PerfilTienda.objects.create(
        user=dueno,
        nombre="Otra tienda",
        direccion="",
        nif="",
        shop=Shop.objects.create(
            name="Otra tienda", opening_cash=Decimal("0.00")
        ),
    )
    membresia(perfil, dueno, "dueno")
    return perfil.shop


@pytest.fixture
def customer(tienda, otra_tienda):
    """A person, trusted in BOTH shops, with a DIFFERENT limit in each."""
    cliente_usuario, cliente = crear_persona("ana", alias="Ana")
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
    return cliente


@pytest.fixture
def api_dueno(owner, tienda):
    """The owner's client, with the shop in its session."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(owner)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


# ---------------------------------------------------------------------------
# The PATCH that writes the limit
# ---------------------------------------------------------------------------


def test_the_owner_sets_the_limit_of_his_own_shop(
    api_dueno, tienda, customer
):
    """The PATCH answers 200 and writes the LINK's limit.

    **Before the fix it answered 500**: `shop_id` was read in `patch`
    and never assigned there.
    """
    respuesta = api_dueno.patch(
        reverse("api:cliente_detalle", args=[customer.id]),
        {"credit_limit": "250.00"},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["credit_limit"] == Decimal("250.00")

    vinculo = Vinculo.objects.get(tienda=tienda, cliente=customer)
    assert vinculo.credit_limit == Decimal("250.00")


def test_the_limit_of_another_shop_is_untouched(
    api_dueno, tienda, otra_tienda, customer
):
    """The limit is PER SHOP: setting it here does not touch it there.

    The trust is the owner's AND it is of that shop. A limit of 250 in
    one shop says nothing about the other one, and the two numbers live
    in two different rows.
    """
    respuesta = api_dueno.patch(
        reverse("api:cliente_detalle", args=[customer.id]),
        {"credit_limit": "250.00"},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.content

    vinculo_otro = Vinculo.objects.get(tienda=otra_tienda, cliente=customer)
    assert vinculo_otro.credit_limit == Decimal("30.00")


def test_the_get_carries_the_limit_of_the_shop_in_the_session(
    api_dueno, tienda, otra_tienda, customer
):
    """The GET reads the limit of ITS shop, not the first one it finds.

    The owner's session names a shop, and that shop's link is the one
    whose limit the answer carries.
    """
    respuesta = api_dueno.get(reverse("api:cliente_detalle", args=[customer.id]))

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["credit_limit"] == Decimal("100.00")


def test_a_null_limit_is_allowed_and_means_no_limit(
    api_dueno, tienda, customer
):
    """`NULL` is **no limit**, and the owner may set it.

    The ceiling is a ceiling: a shop that trusts her without one may
    say so, and `NULL` says exactly that.
    """
    respuesta = api_dueno.patch(
        reverse("api:cliente_detalle", args=[customer.id]),
        {"credit_limit": None},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.content
    vinculo = Vinculo.objects.get(tienda=tienda, cliente=customer)
    assert vinculo.credit_limit is None


def test_a_negative_limit_is_refused(api_dueno, customer):
    """A negative ceiling is no ceiling at all, and a negative number
    is not one."""
    respuesta = api_dueno.patch(
        reverse("api:cliente_detalle", args=[customer.id]),
        {"credit_limit": "-5.00"},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "importe_no_positivo"
