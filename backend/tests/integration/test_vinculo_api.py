"""Slice 10.3 - the link's routes, and the client's consent.

The three questions the API answers:

* **the shop asks** - `POST /api/v1/tienda/vinculos/`;
* **the client answers** - `POST /api/v1/cuenta/vinculos/aceptar/` and
  `.../rechazar/`, **from her own account**;
* **the owner removes** - `DELETE /api/v1/tienda/vinculos/{id}/`, and
  **does not ask**.
"""

from __future__ import annotations

from tests.integration.personas import crear_persona


from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.test import APIClient

from tienda.models import Customer, Vinculo

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def negocio(db):
    """The business, its owner and its shop."""
    from tienda.models import PerfilTienda, Shop

    dueno = User.objects.create_user(username="dueno", password="secreta123")
    tienda = Shop.objects.create(name="Tienda de prueba", opening_cash=Decimal("150.00"))
    perfil = PerfilTienda.objects.create(
        user=dueno, nombre=tienda.name, direccion="", nif="", shop=tienda
    )
    return perfil


@pytest.fixture
def dueno(negocio):
    from tests.conftest import membresia

    membresia(negocio, negocio.user, "dueno")
    return negocio.user


@pytest.fixture
def cliente(db):
    """The PERSON. She belongs to no shop yet."""
    _usuario, persona = crear_persona("ana", alias="Ana")
    return persona


@pytest.fixture
def vinculo(db, negocio, cliente):
    """A pending link: the shop asked, she has not answered."""
    return Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="pendiente",
        credit_limit=Decimal("100.00"),
        pedido_at=__import__("django.utils.timezone", fromlist=["now"]).now(),
        pedido_por=negocio.user,
    )


@pytest.fixture
def api_dueno(dueno, negocio):
    """A client whose session names the shop, and who is the owner."""
    from django.contrib.sessions.backends.db import SessionStore

    cliente = APIClient()
    cliente.force_authenticate(dueno)
    sesion = SessionStore()
    sesion["shop_id"] = negocio.shop.id
    sesion.save()
    cliente.cookies["sessionid"] = sesion.session_key
    return cliente


@pytest.fixture
def api_cliente(cliente):
    """A client whose session is the PERSON's - the client's own.

    **The client's session and the staff's are different kinds**: the
    person's carries no `shop_id`, and that is what keeps it away from
    the staff routes.
    """
    from django.contrib.sessions.backends.db import SessionStore
    from tienda.models import PerfilCliente

    persona = cliente_user(cliente)
    PerfilCliente.objects.create(user=persona)

    api = APIClient()
    api.force_authenticate(persona)
    # The person's session carries NO `shop_id`: a person is not in a
    # shop, and that absence is what keeps it away from the staff
    # routes.
    sesion = SessionStore()
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


def cliente_user(cliente):
    """The person behind the customer row.

    **The person and the customer are the same human**: the alias is
    what joins them, and the seed creates both with the same name.
    """
    return User.objects.create_user(
        username=cliente.alias, password="secreta123"
    )


# ---------------------------------------------------------------------------
# 10.3.3 - The shop asks
# ---------------------------------------------------------------------------


def test_la_tienda_pregunta_y_el_vinculo_queda_pendiente(api_dueno, cliente):
    """The shop asks, and the link waits for HER.

    **The shop cannot accept it for her**: it does not have her
    credentials, and it must not decide for her.
    """
    respuesta = api_dueno.post(
        reverse("api:tienda_vinculos"),
        {"alias": "Ana", "credit_limit": "100.00"},
        format="json",
    )

    assert respuesta.status_code == 201
    vinculo = Vinculo.objects.get(cliente=cliente)
    assert vinculo.estado == "pendiente"
    assert vinculo.credit_limit == Decimal("100.00")


def test_el_dueno_ve_los_vinculos_de_su_tienda(api_dueno, vinculo):
    """The owner sees the links of their shop."""
    respuesta = api_dueno.get(reverse("api:tienda_vinculos"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["estado"] == "pendiente"
    assert cuerpo[0]["alias"] == "Ana"


def test_el_dueno_no_puede_aceptar_el_vinculo(api_dueno, vinculo):
    """The shop does not answer for her.

    **There is no route for it**: the acceptance is the CLIENT's, from
    her account. The owner asking is one thing; the owner deciding is
    another.
    """
    respuesta = api_dueno.post(
        reverse("api:tienda_vinculos"),
        {"alias": "Ana", "credit_limit": "100.00"},
        format="json",
    )

    # The owner's POST creates a PENDING link, never an accepted one.
    assert respuesta.status_code == 201
    assert respuesta.json()["estado"] == "pendiente"


# ---------------------------------------------------------------------------
# 10.3.4 - The client answers
# ---------------------------------------------------------------------------


def test_la_cliente_acepta_el_vinculo(api_cliente, vinculo):
    """She accepts, and the link is accepted.

    **And the limit becomes visible**: the acceptance is what opens the
    owner's figures to her.
    """
    respuesta = api_cliente.post(
        reverse("api:cuenta_vinculo_aceptar"),
        {"vinculo_id": vinculo.id},
        format="json",
    )

    assert respuesta.status_code == 200
    vinculo.refresh_from_db()
    assert vinculo.estado == "aceptado"
    assert vinculo.aceptado_at is not None


def test_la_cliente_rechaza_el_vinculo(api_cliente, vinculo):
    """She refuses, and the link says so."""
    respuesta = api_cliente.post(
        reverse("api:cuenta_vinculo_rechazar"),
        {"vinculo_id": vinculo.id},
        format="json",
    )

    assert respuesta.status_code == 200
    vinculo.refresh_from_db()
    assert vinculo.estado == "rechazado"
    assert vinculo.rechazado_at is not None


def test_la_cliente_ve_solo_el_nombre_de_la_tienda(api_cliente, vinculo):
    """A pending link shows the shop's name and nothing else.

    **If she could see the debt and the ageing first, the consent would
    be a formality**: she would already have seen everything the
    acceptance reveals.
    """
    respuesta = api_cliente.get(reverse("api:cuenta_vinculos"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo) == 1
    pendiente = cuerpo[0]
    assert pendiente["tienda"] == vinculo.tienda.name
    for prohibido in ("credit_limit", "pendiente", "antiguedad_max_dias", "saldo"):
        assert prohibido not in pendiente, f"la peticion lleva {prohibido}"


def test_la_cliente_no_ve_los_vinculos_de_otra_tienda(api_cliente, vinculo, db):
    """The link she answers is the one of the shop she is asked about.

    **She sees HER links**, and no other's.
    """
    respuesta = api_cliente.get(reverse("api:cuenta_vinculos"))

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1


# ---------------------------------------------------------------------------
# 10.3.5 - The owner removes
# ---------------------------------------------------------------------------


def test_el_dueno_elimina_sin_preguntar(api_dueno, vinculo):
    """The owner removes the client - and **does not ask**.

    **The removal is the owner's alone**: the client does not consent to
    being removed, and the shop does not need her to. Her debts and her
    history stay - the book is append-only.
    """
    respuesta = api_dueno.delete(
        reverse("api:tienda_vinculo_eliminar", args=[vinculo.cliente_id])
    )

    assert respuesta.status_code == 200
    vinculo.refresh_from_db()
    assert vinculo.estado == "eliminado"
    assert vinculo.eliminado_at is not None
    # And the person is still there.
    assert Customer.objects.filter(id=vinculo.cliente_id).exists()


def test_el_dueno_re_integra_y_la_cliente_vuelve_a_decidir(api_dueno, vinculo):
    """The owner re-adds the client, and **the client decides again**.

    **The re-integration creates a PENDING link**: the consent does not
    come back by itself.
    """
    Vinculo.objects.filter(id=vinculo.id).update(estado="eliminado")

    respuesta = api_dueno.post(
        reverse("api:tienda_vinculos"),
        {"alias": vinculo.cliente.alias},
        format="json",
    )

    assert respuesta.status_code == 201
    vinculo.refresh_from_db()
    assert vinculo.estado == "pendiente"
    assert vinculo.aceptado_at is None


def test_el_cliente_no_alcanza_las_rutas_del_dueno(api_cliente, vinculo):
    """The client's session does not reach the owner's routes.

    **The boundary.** The person's session carries no `shop_id`, and the
    staff routes need one: a session with no scope is a refusal.
    """
    respuesta = api_cliente.get(reverse("api:tienda_vinculos"))

    assert respuesta.status_code == 403
