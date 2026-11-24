"""The Slice 10.5, T4: **the counter identifies the person**.

**The attendant asks her for her USERNAME and types it.** The system
finds her. That is the whole identification, and it is what the owner
decided: the person is identified with the account she owns, not with a
slip of paper the shop keeps.

**The password is typed by HER, and the owner does not see it.** That
is a **supposition of the process, not a technical guarantee**: the
attendant is behind the counter and she is in front of it, and the
screen the attendant reads carries no password field at all.

**So the counter's search is by username ALONE.** A search that asked
for the password would be a search whose result depends on a secret the
owner does not have - and it would put that secret in a request the
owner can read. The username is public: it is her public name, like an
email address.

**And the answer is HERS.** The counter finds the person and prepares
the fiado; she accepts or refuses it from her own account. The counter
never answers for her.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from tests.conftest import membresia

from tienda.models import (
    Customer,
    PerfilCliente,
    Producto,
    Shop,
    Vinculo,
)


@pytest.fixture
def dueno(db, negocio):
    """The owner, with his membership in the shop.

    **The role lives in the MEMBERSHIP**, so a user without one holds no
    role in any shop and every staff route refuses it.
    """
    membresia(negocio, negocio.user, "dueno")
    return negocio.user


@pytest.fixture
def tienda(db, negocio):
    return negocio.shop


@pytest.fixture
def cliente(tienda, dueno):
    fila = Customer.objects.create(alias="Ana", created_by=dueno)
    Vinculo.objects.create(
        tienda=tienda,
        cliente=fila,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    return fila


@pytest.fixture
def persona(db, cliente):
    """**Her own account**, with a username that is NOT her alias."""
    user = User.objects.create_user(
        username="ana.perez", password="secreta123"
    )
    PerfilCliente.objects.create(user=user)
    cliente.user = user
    cliente.save(update_fields=["user"])
    return user


@pytest.fixture
def api_dueno(dueno, tienda):
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(dueno)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


# ---------------------------------------------------------------------------
# The search
# ---------------------------------------------------------------------------


def test_the_counter_finds_the_person_by_her_username(
    api_dueno, dueno, tienda, cliente, persona
):
    """**The attendant types her username and the system finds her.**

    The username is NOT the alias: the alias is the shop's name for her
    and the username is hers, and they are different strings.
    """
    respuesta = api_dueno.get(
        reverse("api:mostrador_buscar"), {"username": "ana.perez"}
    )

    assert respuesta.status_code == 200, respuesta.content
    filas = respuesta.json()
    assert len(filas) == 1, respuesta.content
    assert filas[0]["alias"] == "Ana"
    assert filas[0]["cliente_id"] == cliente.id


def test_the_search_carries_no_password_field(
    api_dueno, dueno, tienda, persona
):
    """**The search asks for the username ALONE.**

    A search that asked for the password would put a secret the owner
    does not have into a request the owner can read. The password is
    typed by HER, on her own device, and it never travels to the
    counter.
    """
    respuesta = api_dueno.post(
        reverse("api:mostrador_buscar"),
        {"username": "ana.perez", "password": "secreta123"},
        format="json",
    )

    # The password is REFUSED, not ignored: a body that carries it is a
    # mistake, and a mistake that is silently ignored is a mistake that
    # happens again.
    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"


def test_the_search_finds_nobody_when_the_username_is_unknown(
    api_dueno, dueno, tienda
):
    """An unknown username answers with an empty list, not a 404."""
    respuesta = api_dueno.get(
        reverse("api:mostrador_buscar"), {"username": "nadie"}
    )

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json() == []


def test_the_search_only_finds_the_people_of_this_shop(
    api_dueno, dueno, tienda, persona
):
    """**The scope is the shop.**

    The owner of one shop does not get to look for the customers of
    another one - and the person may be a client of several shops, and
    each of them asks her separately.
    """
    otra = Shop.objects.create(
        name="Otra", opening_cash=Decimal("0.00"), currency="EUR"
    )
    ajena = Customer.objects.create(alias="Beto", created_by=dueno)
    Vinculo.objects.create(
        tienda=otra, cliente=ajena, estado="aceptado", credit_limit=None
    )
    usuario = User.objects.create_user(username="beto", password="x")
    PerfilCliente.objects.create(user=usuario)
    ajena.user = usuario
    ajena.save(update_fields=["user"])

    respuesta = api_dueno.get(
        reverse("api:mostrador_buscar"), {"username": "beto"}
    )

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json() == [], (
        "el dueno de una tienda encontro a la clienta de otra"
    )


def test_the_search_does_not_ask_for_the_password_of_somebody_elses_account(
    api_dueno, dueno, tienda, persona
):
    """**The search never authenticates anybody.**

    It finds a person; it does not sign her in. The answer to the fiado
    is hers, from her own account, and the counter has no way to answer
    for her - so it has no way to pretend she did.
    """
    respuesta = api_dueno.get(
        reverse("api:mostrador_buscar"), {"username": "ana.perez"}
    )

    assert respuesta.status_code == 200, respuesta.content
    cuerpo = respuesta.json()
    assert isinstance(cuerpo, list)
    for fila in cuerpo:
        assert "password" not in fila
        assert "contrasena" not in fila


def test_a_person_without_an_account_is_not_found_by_username(
    api_dueno, dueno, tienda, cliente
):
    """**Only a person with an ACCOUNT is found by username.**

    The counter identifies the person by the account she owns, and a
    customer row without one is not identified that way. The shop still
    has her in its list - the alias finds her - but the counter's
    identification is the account.
    """
    respuesta = api_dueno.get(
        reverse("api:mostrador_buscar"), {"username": "Ana"}
    )

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json() == []
