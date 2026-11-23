"""The person's account and her customer row: they are the SAME human,
and the link between them is a STRING.

**The bug this file pins.** `Customer` has no `user` field. The person
chooses her own username when she registers, and the shop calls her by
an ALIAS - "Ana" - which is not a username at all. The only thing that
joined the two was `_cliente_de`, which looked for
`Customer.objects.filter(alias=user.username)`.

So the client's own account only worked when her username happened to
BE her alias: "Ana" registered as "Ana". And the person chooses her
username - that is the whole point of the 10.1 - so a person who
registered as "ana.perez" and is called "Ana" by the shop saw **no
links at all**: her consent could not be given, because the shop's
question was addressed to a customer row her account could not find.

The person's customer row and her account are the same human, and the
model has to say so.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.conftest import membresia

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from tienda.models import (
    Customer,
    PerfilCliente,
    PerfilTienda,
    Shop,
    Vinculo,
)


@pytest.fixture
def owner(db, negocio):
    membresia(negocio, negocio.user, "dueno")
    return negocio.user


@pytest.fixture
def tienda(db, negocio):
    return negocio.shop


@pytest.fixture
def cliente(tienda):
    """The customer row: the shop calls her "Ana"."""
    return Customer.objects.create(alias="Ana")


@pytest.fixture
def persona(db, cliente):
    """**A person whose username is NOT her alias.**

    This is the real case: she chooses her username when she registers,
    and the shop calls her by an alias. The two are different things.
    """
    user = User.objects.create_user(
        username="ana.perez", password="secreta123"
    )
    PerfilCliente.objects.create(user=user)
    return user


@pytest.fixture
def persona_reclamada(persona, cliente):
    """The person, and the row she claims: the shop registered her
    before she had an account, and she takes the row now."""
    from tienda.services import reclamar_cliente

    reclamar_cliente(persona, cliente.alias)
    return persona


@pytest.fixture
def api_persona(persona):
    """The client of the person's own account."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(persona)
    sesion = SessionStore()
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


def test_the_person_claims_the_row_the_shop_created_for_her(
    api_persona, persona, cliente, tienda
):
    """**The claim is the meeting.** The shop registered her before she
    had an account; she takes the row now.

    Before the fix there was no way to do this at all: the account found
    the row by `alias == username`, and "ana.perez" is not "Ana".
    """
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="pendiente",
        pedido_at=timezone.now(),
    )

    assert cliente.user_id is None

    respuesta = api_persona.post(
        reverse("api:cuenta_reclamar"),
        {"alias": "Ana"},
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.content
    cliente.refresh_from_db()
    assert cliente.user_id == persona.id


def test_the_person_sees_her_links_after_claiming_the_row(
    api_persona, persona_reclamada, cliente, tienda
):
    """Her account finds her customer row, whatever she is called.

    Before the fix the answer was an EMPTY list: the lookup was
    `alias=user.username`, and "ana.perez" is not "Ana".
    """
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="pendiente",
        pedido_at=timezone.now(),
    )

    respuesta = api_persona.get(reverse("api:cuenta_vinculos"))

    assert respuesta.status_code == 200, respuesta.content
    vinculos = respuesta.json()
    assert len(vinculos) == 1, respuesta.content
    assert vinculos[0]["tienda"] == tienda.name


def test_the_person_accepts_a_link_after_claiming_the_row(
    api_persona, persona_reclamada, cliente, tienda
):
    """**The consent is the whole point**, and it has to reach her.

    The shop asked; the question is addressed to her customer row. If
    her account cannot find that row, she can never answer, and the
    shop's question waits forever.
    """
    vinculo = Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="pendiente",
        pedido_at=timezone.now(),
    )

    respuesta = api_persona.post(
        reverse("api:cuenta_vinculo_aceptar"),
        {"vinculo_id": vinculo.id},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.content
    vinculo.refresh_from_db()
    assert vinculo.estado == "aceptado"


def test_a_row_that_is_already_claimed_is_not_taken_again(
    api_persona, persona_reclamada, cliente, tienda
):
    """**A person is ONE row.** The uniqueness is a constraint.

    And the refusal does not say whether the row does not exist or
    belongs to somebody else: the answer is the same either way.
    """
    otra = User.objects.create_user(username="otra", password="secreta123")
    PerfilCliente.objects.create(user=otra)

    respuesta = api_persona.post(
        reverse("api:cuenta_reclamar"),
        {"alias": "Ana"},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "alias_no_reclamable"

    cliente.refresh_from_db()
    assert cliente.user_id == persona_reclamada.id


def test_the_claim_needs_the_alias(api_persona):
    """An empty alias is refused."""
    respuesta = api_persona.post(
        reverse("api:cuenta_reclamar"),
        {"alias": "  "},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "alias_requerido"
