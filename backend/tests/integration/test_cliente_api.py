"""The client's own surface - tasks 6.1, 6.2 and 6.3.

The client reads its own statement and proposes a payment. It never
writes to the book: the charge exists only at the confirmation, which
happens in the shop, with the staff session.

The cases, and where each comes from:

* the statement holds **that customer's own confirmed charges**, each with
  its full `lineas[]` - the v1 rule "the itemisation lives only inside
  the action" is gone, because the client confirms in the shop and
  therefore sees the `desglose` before the charge exists (CC-02, CC-06);
* each charge carries `pagado` and `saldo`, derived on read from the
  `ImputacionPago` rows - against charges of 8,00, 7,00 and 15,00 with
  a payment of 20,00 the statement reads 8/8, 7/7 and 5/15, with 10,00
  still owed (PA-02, ADR-27);
* a charge outside the customer's scope is refused with `cargo_ajeno` and
  returns no data (CAC-10);
* the credential sets no cookie (R4);
* **the client never writes to the ledger**: a client-authenticated
  request creates no `LedgerEntry`, no `CargoLinea`, no `Confirmacion`
  and no `FiadoPropuesto` (CAC-03, CC-07);
* the routes that are gone answer 404: `POST /api/v1/cliente/confirmar/`,
  `POST /api/v1/cliente/disputar/` and `POST /api/v1/facilitar/{id}/`
  (design 9.1).

A note on the harness. The credential is presented in the `X-Codigo`
header, and the client is resolved from it. The tests that matter assert
on the **effect** - the rows written, the payload returned - and the
status code is a companion, never the proof: the Phase 4 slice found that
a status-code assertion could not distinguish "resolved" from "not
resolved", because a pending view answers 501 either way.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.api import client_auth
from tienda.models import (
    CargoLinea,
    Confirmacion,
    Customer,
    CustomerCodigo,
    FiadoPropuesto,
    LedgerEntry,
    Producto,
    Shop,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def tienda(db):
    return Shop.objects.create(name="Tienda de prueba", opening_cash=Decimal("150.00"))


@pytest.fixture
def otra_tienda(db):
    return Shop.objects.create(name="Otra tienda", opening_cash=Decimal("0.00"))


@pytest.fixture
def customer(tienda):
    return Customer.objects.create(
        shop=tienda, alias="Ana", credit_limit=Decimal("100.00")
    )


@pytest.fixture
def otro_customer(tienda):
    return Customer.objects.create(
        shop=tienda, alias="Beto", credit_limit=Decimal("100.00")
    )


@pytest.fixture
def producto(tienda):
    return Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )


@pytest.fixture
def credencial(db, tienda, customer, user):
    """An ACTIVE credential of a customer."""
    valor = client_auth.generar_credencial()
    fila = CustomerCodigo.objects.create(
        shop=tienda,
        customer=customer,
        prefix=client_auth.prefijo_de(valor),
        codigo_hash=client_auth.hashear_credencial(valor),
        issued_at=timezone.now(),
        issued_by=user,
    )
    return valor, fila


@pytest.fixture
def api_cliente():
    """A client that presents a credential in the header.

    The credential travels in the `X-Codigo` header, and Django's test
    client takes a custom header as the `HTTP_` prefixed form. The
    `APIClient.credentials()` method is NOT it: that one builds an HTTP
    authentication header, and the credential would never arrive.
    """

    def _api(valor):
        api = APIClient()
        api.defaults["HTTP_X_CODIGO"] = valor
        return api

    return _api


def _cargo(tienda, customer, user, producto, *, cantidad="3", precio="1.00", when=None):
    """A CONFIRMED charge, with its lines and its confirmation."""
    momento = when or timezone.now()
    cargo = LedgerEntry.objects.create(
        shop=tienda,
        customer=customer,
        user=user,
        kind="cargo",
        amount=Decimal(cantidad) * Decimal(precio),
        occurred_at=momento,
    )
    CargoLinea.objects.create(
        cargo=cargo,
        producto=producto,
        cantidad=Decimal(cantidad),
        precio_unitario=Decimal(precio),
        total=Decimal(cantidad) * Decimal(precio),
    )
    Confirmacion.objects.create(
        cargo=cargo,
        estado="confirmado",
        confirmado_en=momento,
        origen="tienda",
    )
    return cargo


# ---------------------------------------------------------------------------
# 6.1 - The statement
# ---------------------------------------------------------------------------


def test_the_statement_holds_the_own_confirmed_charges(
    api_cliente, credencial, tienda, customer, user, producto
):
    """CC-02, CC-06: the statement holds the client's own charges.

    Each one carries its full `lineas[]`: the v1 rule "the itemisation
    lives only inside the action" is gone, because the client confirms in
    the shop and therefore sees the `desglose` before the charge exists.
    """
    valor, _ = credencial
    cargo = _cargo(tienda, customer, user, producto)

    respuesta = api_cliente(valor).get(reverse("api:cliente_estado"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["alias"] == "Ana"
    assert len(cuerpo["cargos"]) == 1
    cargo_leido = cuerpo["cargos"][0]
    assert cargo_leido["id"] == cargo.id
    assert len(cargo_leido["lineas"]) == 1
    assert cargo_leido["lineas"][0]["producto"] == "Pan"
    assert cargo_leido["lineas"][0]["cantidad"] == "3.000"
    assert cargo_leido["lineas"][0]["total"] == "3.00"


def test_the_statement_carries_no_staff_field(api_cliente, credencial):
    """CAC-10: the statement declares none of the nine staff-only fields.

    The guarantee is about the SCHEMA, not about the view: DRF's `fields`
    is exhaustive, so a field that is not declared cannot be in the
    response whatever the view hands over.
    """
    from tienda.api.serializers.cliente import verificar_aislamiento_del_cliente

    assert verificar_aislamiento_del_cliente() == set()


def test_the_statement_holds_only_the_own_customer(
    api_cliente, credencial, tienda, customer, otro_customer, user, producto
):
    """CAC-10: the statement never carries another customer's data."""
    valor, _ = credencial
    _cargo(tienda, otro_customer, user, producto)

    respuesta = api_cliente(valor).get(reverse("api:cliente_estado"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["cargos"] == []
    assert "Beto" not in str(cuerpo)


def test_a_charge_of_another_customer_is_refused(
    api_cliente, credencial, tienda, otro_customer, user, producto
):
    """A charge outside the customer's scope is refused with `cargo_ajeno`.

    And it returns NO data: the refusal is not a charge with the fields
    blanked.
    """
    valor, _ = credencial
    cargo = _cargo(tienda, otro_customer, user, producto)

    respuesta = api_cliente(valor).get(
        reverse("api:cliente_cargo", args=[cargo.id])
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "cargo_ajeno"
    assert "lineas" not in str(respuesta.json())


def test_the_own_charge_is_read_with_its_itemisation(
    api_cliente, credencial, tienda, customer, user, producto
):
    """CC-02: `GET /api/v1/cliente/cargos/{id}/` shows the full itemisation."""
    valor, _ = credencial
    cargo = _cargo(tienda, customer, user, producto)

    respuesta = api_cliente(valor).get(
        reverse("api:cliente_cargo", args=[cargo.id])
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id"] == cargo.id
    assert len(cuerpo["lineas"]) == 1
    assert cuerpo["lineas"][0]["producto"] == "Pan"


def test_the_credential_sets_no_cookie(api_cliente, credencial):
    """R4: the credential travels in the header and leaves no cookie.

    A credential that reached a cookie would reach every request of the
    browser, and its own request.
    """
    valor, _ = credencial

    respuesta = api_cliente(valor).get(reverse("api:cliente_estado"))

    assert respuesta.status_code == 200
    assert not respuesta.cookies


# ---------------------------------------------------------------------------
# 6.1 - The paid/pending split
# ---------------------------------------------------------------------------


def test_the_statement_reads_the_paid_and_pending_split(
    api_cliente, credencial, tienda, customer, user, producto
):
    """PA-02, ADR-27: the statement reads `pagado` and `saldo` per charge.

    Three charges of 8,00, 7,00 and 15,00 with a payment of 20,00: the
    statement reads 8/8, 7/7 and 5/15, and 10,00 is still owed. The
    repartition is RECORDED in the `ImputacionPago` rows, and the split
    is derived on read from them - never stored on the charge.
    """
    valor, _ = credencial

    # Three charges, oldest first: the FIFO applies to them in that
    # order. They are stamped in the PAST, because the server stamps a
    # charge at the confirmation instant and a charge in the future is
    # a charge that has not happened yet.
    base = timezone.now() - timezone.timedelta(minutes=10)
    cargos = []
    for i, importe in enumerate(("8.00", "7.00", "15.00")):
        cargo = LedgerEntry.objects.create(
            shop=tienda,
            customer=customer,
            user=user,
            kind="cargo",
            amount=Decimal(importe),
            occurred_at=base + timezone.timedelta(minutes=i),
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
            confirmado_en=base + timezone.timedelta(minutes=i),
            origen="tienda",
        )
        cargos.append(cargo)

    # A payment of 20,00, retired against the three charges FIFO.
    pago = LedgerEntry.objects.create(
        shop=tienda,
        customer=customer,
        user=user,
        kind="pago",
        amount=Decimal("20.00"),
        occurred_at=base + timezone.timedelta(minutes=5),
    )
    from tienda.models import ImputacionPago

    ImputacionPago.objects.create(pago=pago, cargo=cargos[0], importe=Decimal("8.00"))
    ImputacionPago.objects.create(pago=pago, cargo=cargos[1], importe=Decimal("7.00"))
    ImputacionPago.objects.create(pago=pago, cargo=cargos[2], importe=Decimal("5.00"))

    respuesta = api_cliente(valor).get(reverse("api:cliente_estado"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    leidos = {c["id"]: c for c in cuerpo["cargos"]}

    assert leidos[cargos[0].id]["pagado"] == "8.00"
    assert leidos[cargos[0].id]["saldo"] == "0.00"
    assert leidos[cargos[1].id]["pagado"] == "7.00"
    assert leidos[cargos[1].id]["saldo"] == "0.00"
    assert leidos[cargos[2].id]["pagado"] == "5.00"
    assert leidos[cargos[2].id]["saldo"] == "10.00"
    assert cuerpo["total"] == "10.00"


# ---------------------------------------------------------------------------
# 6.2 - The client never writes to the book
# ---------------------------------------------------------------------------


def test_cliente_no_escribe_en_la_libreta(
    api_cliente, credencial, tienda, customer, user, producto
):
    """CAC-03, CC-07: a client request writes NOTHING to the book.

    The only row a client request may create is its own `PagoPropuesto`.
    This is the v2 invariant that replaces the v1 dispute tests: the
    client has no write scope at all, so there is nothing to dispute.

    **The companion matters.** The reads must SUCCEED, otherwise the
    assertion would be true for the wrong reason: a route that does
    nothing also writes nothing. The two assertions together say what
    the test means - the client read its statement, and reading wrote
    nothing.
    """
    valor, _ = credencial
    cargo = _cargo(tienda, customer, user, producto)

    api = api_cliente(valor)
    estado = api.get(reverse("api:cliente_estado"))
    detalle = api.get(reverse("api:cliente_cargo", args=[cargo.id]))

    # The reads happened: the statement was served and it carried the
    # client's own charge.
    assert estado.status_code == 200
    assert len(estado.json()["cargos"]) == 1
    assert detalle.status_code == 200

    # And none of it wrote to the book.
    assert LedgerEntry.objects.count() == 1  # the charge that already existed
    assert CargoLinea.objects.count() == 1
    assert Confirmacion.objects.count() == 1
    assert FiadoPropuesto.objects.count() == 0


def test_a_staff_session_cannot_reach_a_client_route(
    api_cliente, credencial, tienda, customer, user, producto
):
    """CAC-03: there is no upgrade in either direction.

    A staff session carrying a valid credential is refused: a client
    route refuses a staff session, and a staff route refuses a client.
    """
    valor, _ = credencial
    _cargo(tienda, customer, user, producto)

    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(user)
    api.credentials(**{client_auth.CABECERA: valor})
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    respuesta = api.get(reverse("api:cliente_estado"))

    assert respuesta.status_code == 403


def test_an_unknown_credential_is_refused(api_cliente, tienda, customer):
    """The refusal never says whether the credential existed."""
    valor = client_auth.generar_credencial()

    respuesta = api_cliente(valor).get(reverse("api:cliente_estado"))

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "codigo_invalido"
    assert customer.alias not in str(respuesta.json())


def test_a_missing_credential_is_refused(api_cliente):
    """No credential at all is the same refusal."""
    respuesta = api_cliente("").get(reverse("api:cliente_estado"))

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "codigo_invalido"


# ---------------------------------------------------------------------------
# 6.3 - The routes that are gone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ruta",
    [
        "/api/v1/cliente/confirmar/",
        "/api/v1/cliente/disputar/",
        "/api/v1/facilitar/1/",
    ],
)
def test_the_removed_routes_do_not_exist(api_cliente, credencial, ruta):
    """CC-01, CAC-03: the routes that are gone answer 404.

    A 404 and not a 403: the route does not exist, so there is no
    capability to refuse. A client can reach no write endpoint.
    """
    valor, _ = credencial

    respuesta = api_cliente(valor).post(ruta, {}, format="json")

    assert respuesta.status_code == 404
