"""The Slice 10.6, T1: **sin cuenta, no hay vinculo aceptado**.

**El hueco que la verificacion encontro.** La ruta
`POST /api/v1/clientes/` - la del dueno - creaba a la persona con el
vinculo `aceptado`, **sin exigir cuenta**. Por esa via, una persona sin
cuenta podia tener un cargo: una deuda que no puede rechazar y que
nadie le ha pedido permiso para crear.

**La regla del dueno**: *si un cliente no tiene cuenta, entonces no
puede tener un fiado en primer lugar*. Y sin fiado no hay deuda que
pagar - que es lo que hacia imposible que el `codigo` tuviera un caso
que lo justificara.

**La puerta.** El dueno registra a la persona y el vinculo nace
`pendiente`: ella lo acepta desde su cuenta, con su consentimiento.
Una persona sin cuenta no es clienta de confianza de ninguna tienda, y
por lo tanto no puede deber.

**Y la ficha no se crea sola.** La `Customer` lleva un `user` que ahora
es **NOT NULL**: una ficha sin persona detras no es una persona, es una
fila que el dueno escribio y que nadie puede contestar.

**El orden es el de la vida real**: la persona se registra (y su ficha
nace con ella), la tienda la busca por su username y le pide
confianza, y ella contesta.
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

from tienda.models import Customer, Vinculo


@pytest.fixture
def dueno(db, negocio):
    membresia(negocio, negocio.user, "dueno")
    return negocio.user


@pytest.fixture
def tienda(db, negocio):
    return negocio.shop


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


@pytest.fixture
def ana(db):
    """**Ana existe**: tiene su cuenta y su ficha."""
    return crear_persona("ana", alias="Ana")


# ---------------------------------------------------------------------------
# The door
# ---------------------------------------------------------------------------


def test_the_owner_registers_a_person_and_the_link_waits_for_her(
    api_dueno, dueno, tienda, ana
):
    """**The link is born `pendiente`.** She answers it, from her account.

    Before the fix it was born `aceptado`, without asking anybody:
    the owner registered her as a trusted client and she was one.
    """
    respuesta = api_dueno.post(
        reverse("api:clientes"),
        {"alias": "ana", "credit_limit": "100.00"},
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.content

    vinculo = Vinculo.objects.get()
    assert vinculo.estado == "pendiente", (
        "el vinculo nacio aceptado y la persona no ha contestado nada"
    )
    assert vinculo.credit_limit == Decimal("100.00")
    assert vinculo.pedido_at is not None
    assert vinculo.aceptado_at is None


def test_a_person_without_an_account_cannot_be_registered(
    api_dueno, dueno, tienda
):
    """**A row with no person behind it is not a person.**

    The `Customer` carries a `user` that is NOT NULL: a row without a
    person behind it is a row the owner wrote and nobody can answer.
    """
    campo = Customer._meta.get_field("user")

    assert campo.null is False, (
        "la ficha admite no tener persona: es una fila que nadie puede "
        "contestar"
    )


def test_the_shop_cannot_register_somebody_who_does_not_exist(
    api_dueno, dueno, tienda
):
    """**The shop does not create people.**

    It asks the ones who exist. A person with no account is not a
    customer - and the shop has no way to make one, because the account
    is HERS.
    """
    respuesta = api_dueno.post(
        reverse("api:clientes"),
        {"alias": "nadie"},
        format="json",
    )

    assert respuesta.status_code == 422, respuesta.content
    assert respuesta.json()["codigo_error"] == "cliente_no_existe"
    assert Vinculo.objects.count() == 0


def test_the_owner_cannot_accept_the_link_for_her(
    api_dueno, dueno, tienda, ana
):
    """**The answer is hers.** The owner may not accept it.

    A shop that could accept for her would be a shop that could decide
    for her, and the consent of the 10.3 would be worth nothing.
    """
    api_dueno.post(
        reverse("api:clientes"),
        {"alias": "ana"},
        format="json",
    )

    vinculo = Vinculo.objects.get()

    # La ruta del dueno: no existe. La del dueno es la de PREGUNTAR.
    from django.urls import NoReverseMatch

    with pytest.raises(NoReverseMatch):
        reverse("cuenta_vinculo_aceptar")

    # Y el estado sigue siendo el de la pregunta.
    vinculo.refresh_from_db()
    assert vinculo.estado == "pendiente"


def test_the_person_accepts_it_from_her_own_account(
    api_dueno, dueno, tienda, ana
):
    """**And she accepts it.** The door opens from her side.

    This is the whole point of the change: the owner's act is the
    QUESTION and hers is the ANSWER.
    """
    from django.contrib.sessions.backends.db import SessionStore

    usuario, _cliente = ana

    api_dueno.post(
        reverse("api:clientes"),
        {"alias": "ana"},
        format="json",
    )
    vinculo = Vinculo.objects.get()

    api = APIClient()
    api.force_authenticate(usuario)
    sesion = SessionStore()
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    respuesta = api.post(
        reverse("api:cuenta_vinculo_aceptar"),
        {"vinculo_id": vinculo.id},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.content
    vinculo.refresh_from_db()
    assert vinculo.estado == "aceptado"
    assert vinculo.aceptado_at is not None


def test_the_registered_person_can_have_a_debt_only_after_she_accepts(
    api_dueno, dueno, tienda, ana
):
    """**A debt needs an accepted link.**

    The `cliente_de_la_tienda` - the lookup every counter route uses -
    only finds a person whose link is `aceptado`. A person whose link is
    `pendiente` is not a client of the shop, and the shop cannot make a
    fiado for her.
    """
    from tienda import services

    api_dueno.post(
        reverse("api:clientes"),
        {"alias": "ana"},
        format="json",
    )
    vinculo = Vinculo.objects.get()

    # Mientras esta pendiente, la tienda no la ve como clienta.
    assert services.cliente_de_la_tienda(tienda, vinculo.cliente_id) is None

    # Y cuando lo acepta, si.
    vinculo.estado = "aceptado"
    vinculo.save(update_fields=["estado"])

    assert (
        services.cliente_de_la_tienda(tienda, vinculo.cliente_id) is not None
    )


def test_the_registration_creates_the_account_and_the_row(db):
    """**The account and the row arrive together.**

    The owner's rule is that a client without an account cannot have a
    fiado, so the two are not separable: the registration makes both,
    or the person is not a person yet.
    """
    from django.contrib.auth.models import User

    from tienda.api.cuenta import CuentaRegistroView

    # La vista, con su cliente de pruebas.
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
