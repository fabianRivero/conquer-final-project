"""The Slice 10.4: **the person and her row are the same human**.

**The claim is GONE** - and it went in the 10.6, because the owner's
rule closed the door it was guarding: *a client without an account
cannot have a fiado*. If the row cannot exist without a person, there
is nothing to claim.

**What replaces it**: the person creates the account AND her row, in the
same registration. The account and the row are not separable, because
the owner's rule makes the second useless without the first.

**What stays**: the account and the row are the same human, and the
model says so - `Customer.user` is a OneToOne, and a row without a
person behind it is not a person.
"""


from __future__ import annotations

from tests.integration.personas import crear_persona

from decimal import Decimal

import pytest

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from tests.conftest import membresia

from tienda.models import Customer, PerfilTienda, Shop, Vinculo


@pytest.fixture
def dueno(db, negocio):
    membresia(negocio, negocio.user, "dueno")
    return negocio.user


@pytest.fixture
def tienda(db, negocio):
    return negocio.shop


@pytest.fixture
def otra_tienda(db):
    """A SECOND shop, with its own owner and its own business."""
    dueno = User.objects.create_user(username="dueno2", password="x")
    perfil = PerfilTienda.objects.create(
        user=dueno,
        nombre="Otra",
        direccion="",
        nif="",
        shop=Shop.objects.create(
            name="Otra", opening_cash=Decimal("0.00"), currency="EUR"
        ),
    )
    membresia(perfil, dueno, "dueno")
    return perfil.shop


@pytest.fixture
def persona(db):
    """**La persona**: su cuenta y su ficha."""
    return crear_persona("ana.perez", alias="Ana")


@pytest.fixture
def cliente(persona):
    """**Su ficha**: la fila que es ella en el mundo del credito."""
    return persona[1]


@pytest.fixture
def api_persona(persona):
    """The client of the person's own account - a session, no `shop_id`."""
    from django.contrib.sessions.backends.db import SessionStore

    usuario, _cliente = persona

    api = APIClient()
    api.force_authenticate(usuario)
    sesion = SessionStore()
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


# ---------------------------------------------------------------------------
# The row and the account are the same human
# ---------------------------------------------------------------------------


def test_the_registration_makes_the_account_and_the_row(db):
    """**The account and the row arrive together.**

    The owner's rule makes them inseparable: a row without a person
    behind it is a row nobody can answer.
    """
    api = APIClient()
    respuesta = api.post(
        reverse("api:cuenta_registro"),
        {"username": "ana.perez", "password": "secreta123", "alias": "Ana"},
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.content

    usuario = User.objects.get(username="ana.perez")
    cliente = Customer.objects.get(user=usuario)
    assert cliente.alias == "Ana"
    assert cliente.user_id == usuario.id


def test_the_row_points_at_the_person_and_the_person_at_the_row(db):
    """**The two are the same human**, and the model says so.

    `Customer.user` is a OneToOne: a person is ONE row, wherever she
    buys on credit.
    """
    usuario, cliente = crear_persona("ana.perez", alias="Ana")

    assert cliente.user_id == usuario.id
    # Y del otro lado: el usuario tiene ESA fila y no otra.
    assert usuario.customer.id == cliente.id


def test_a_second_row_for_the_same_person_is_refused(db):
    """**A person is ONE row.** The uniqueness is a constraint."""
    from django.db import IntegrityError, transaction

    usuario, _cliente = crear_persona("ana.perez", alias="Ana")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.create(
                user=usuario,
                alias="Ana otra vez",
                created_by=usuario,
            )


# ---------------------------------------------------------------------------
# What she does with her row
# ---------------------------------------------------------------------------


def test_the_person_sees_her_links(
    api_persona, persona, cliente, tienda, otra_tienda, dueno
):
    """**Her links, and the figures of each shop.**

    The link she accepted opens the owner's figures to her: how much she
    owes THERE, how old the debt is THERE, and the limit the owner gave
    her THERE.
    """
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

    respuesta = api_persona.get(reverse("api:cuenta_vinculos"))

    assert respuesta.status_code == 200, respuesta.content
    filas = {f["tienda"]: f for f in respuesta.json()}
    assert filas["Tienda de prueba"]["credit_limit"] == Decimal("100.00")
    assert filas["Otra"]["credit_limit"] == Decimal("30.00")


def test_the_person_accepts_a_link_from_her_own_account(
    api_persona, persona, cliente, tienda, dueno
):
    """**The answer is hers.** She accepts the shop's question.

    Before the 10.6 this was a two-step dance - the shop registered her
    and she CLAIMED the row. Now the row is hers from the start, and
    the answer is the only step that is left.
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
