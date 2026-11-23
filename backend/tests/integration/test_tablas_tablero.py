"""The three lists the board reads beside the board itself.

The design's route table names them, and the board's components are
written against their REAL shapes:

* `/api/v1/clientes/` - the credit book's list, with the credential's
  state: the `prefix` - the NON-SECRET head of it - and the issuing
  date. Both are the OWNER's own data;
* `/api/v1/catalogo/` - the goods eligible for fiado, with the
  product's id, because the proposal form has to name the product it is
  selling;
* `/api/v1/pagos-propuestos/` - the client's proposed payments, PENDING
  only. The board's section is a work list: what waits for the owner's
  decision.

A note on the shapes: the three answer a BARE LIST, not a paginated
object with `results`. A component that reads `results` would show
nothing, and nothing would look like "there is nothing to show".
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.conftest import membresia
from django.contrib.auth.models import Group, User
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client
from django.utils import timezone

from tienda.api import client_auth
from tienda.models import (
    Customer,
    CustomerCodigo,
    PagoPropuesto,
    Producto,
    Shop,
    Vinculo,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def owner(db, negocio):
    user = negocio.user
    membresia(negocio, user, "dueno")
    return user


@pytest.fixture
def tienda(db, owner, negocio):
    """The shop of the credit book - the business's own shop."""
    return negocio.shop


@pytest.fixture
def api(owner, tienda):
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    cliente = Client()
    cliente.cookies["sessionid"] = sesion.session_key
    cliente.force_login(owner)
    return cliente


def test_la_lista_de_clientes_lleva_el_estado_de_la_credencial(api, tienda, owner):
    """The list carries the credential's `prefix` and its issuing date.

    The `prefix` is six symbols of the alphabet and cannot resolve to a
    credential without the digest, and the digest never leaves the
    credential's table. Both fields are the OWNER's own data, and the
    board reads them in one response instead of one per customer.
    """
    cliente = Customer.objects.create(alias="Ana")
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    valor = client_auth.generar_credencial()
    CustomerCodigo.objects.create(
        shop=tienda,
        customer=cliente,
        prefix=client_auth.prefijo_de(valor),
        codigo_hash=client_auth.hashear_credencial(valor),
        issued_at=timezone.now(),
        issued_by=owner,
    )

    respuesta = api.get("/api/v1/clientes/")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    # A BARE LIST, not a paginated object.
    assert isinstance(cuerpo, list)
    fila = cuerpo[0]
    assert fila["alias"] == "Ana"
    assert fila["prefix"] == client_auth.prefijo_de(valor)
    assert fila["issued_at"] is not None
    # And the digest NEVER leaves the table.
    assert "codigo_hash" not in fila
    assert valor not in str(cuerpo)


def test_la_lista_del_catalogo_lleva_el_id(api, tienda):
    """The catalogue carries the product's id.

    The proposal form has to name the product it is selling, and the id
    of a product of the OWNER's own catalogue is not a secret: it is not
    one of the nine staff-only fields.
    """
    Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.20"), unidad="unidad"
    )

    respuesta = api.get("/api/v1/catalogo/")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert isinstance(cuerpo, list)
    assert cuerpo[0]["id"]
    assert cuerpo[0]["nombre"] == "Pan"
    # The price comes back as a number, not as a string.
    assert float(cuerpo[0]["precio"]) == 1.20


def test_la_lista_de_pagos_propuestos_solo_los_pendientes(api, tienda, owner):
    """Only the PENDING proposals are listed.

    The board's section is a work list: a proposal that was validated or
    rejected is history.
    """
    cliente = Customer.objects.create(alias="Ana")
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    pendiente = PagoPropuesto.objects.create(
        shop=tienda,
        customer=cliente,
        importe=Decimal("5.00"),
        referencia="billete",
        estado="pendiente",
        created_at=timezone.now(),
    )
    resuelto = PagoPropuesto.objects.create(
        shop=tienda,
        customer=cliente,
        importe=Decimal("3.00"),
        estado="validado",
        created_at=timezone.now(),
        # A resolved proposal names who resolved it and when - the
        # model's own CHECK demands it.
        resolved_at=timezone.now(),
        resolved_by=owner,
    )

    respuesta = api.get("/api/v1/pagos-propuestos/")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert isinstance(cuerpo, list)
    assert len(cuerpo) == 1
    assert cuerpo[0]["id"] == pendiente.id
    assert cuerpo[0]["alias"] == "Ana"
    # The amount comes back as a number, not as a string.
    assert float(cuerpo[0]["importe"]) == 5.00
    assert cuerpo[0]["estado"] == "pendiente"
    assert resuelto.id not in [pago["id"] for pago in cuerpo]


def test_la_lista_de_pagos_propuestos_es_del_dueno(api, tienda, negocio):
    """The `dependiente` does not reach the proposed payments.

    The credit book is the owner's alone.
    """
    dependiente = User.objects.create_user(username="dependiente", password="x")
    membresia(negocio, dependiente, "dependiente")

    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    otro = Client()
    otro.cookies["sessionid"] = sesion.session_key
    otro.force_login(dependiente)

    respuesta = otro.get("/api/v1/pagos-propuestos/")

    assert respuesta.status_code == 403
