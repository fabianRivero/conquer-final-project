"""The ledger and the catalogue — tasks 4.4 and 4.5.

**The ledger.** `POST /api/v1/clientes/{id}/libreta/` is the only way a
payment is written, and it accepts `kind` ∈ {`pago`} **only**: a `cargo` is
written by the confirmation of a proposal, never directly. That is the
v2 model — the charge exists only at the confirmation (ADR-19).

The cases:

* the request may not carry `occurred_at` (rule 4);
* a non-positive amount is refused with `importe_no_positivo` (rule 15);
* an unknown kind is refused with `tipo_desconocido` (rule 16);
* a `pago` larger than the outstanding is refused with `pago_excede_deuda`
  (rule 19) — **and the excess is change, never a credit**;
* a refused write creates **no row**.

**The catalogue.** `GET /api/v1/catalogo/` is the owner's, it exposes only
the goods eligible for fiado, and the `dependiente` gets 403. The
catalogue price is a **default**: a line carries the price actually
charged, and a later change to the catalogue never rewrites a stored line
(IC-08).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.conftest import membresia
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.models import Customer, LedgerEntry, Producto, Shop, Vinculo

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner(db, negocio):
    user = negocio.user
    membresia(negocio, user, "dueno")
    return user


@pytest.fixture
def helper(db, negocio):
    user = User.objects.create_user(username="dependiente", password="x")
    membresia(negocio, user, "dependiente")
    return user


def _sesion(api, tienda):
    """Give the client a session that names the shop."""
    from django.contrib.sessions.backends.db import SessionStore

    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


@pytest.fixture
def tienda(db, negocio):
    """The shop of the credit book - the business's own shop."""
    return negocio.shop


@pytest.fixture
def cliente(owner, tienda):
    api = APIClient()
    api.force_authenticate(owner)
    return _sesion(api, tienda)


@pytest.fixture
def customer(tienda):
    """A person, and the LINK that says she is a trusted client of the shop.

    **The person belongs to no shop**, and the limit belongs to the link.
    """
    cliente = Customer.objects.create(alias="Ana")
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    return cliente


@pytest.fixture
def producto(tienda):
    return Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.20"), unidad="unidad"
    )


@pytest.fixture
def cargo(tienda, customer, owner):
    """A confirmed charge of 30,00 € — the debt the payment retires."""
    return LedgerEntry.objects.create(
        shop=tienda,
        customer=customer,
        user=owner,
        kind="cargo",
        amount=Decimal("30.00"),
        occurred_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


def test_a_payment_is_recorded(cliente, customer, cargo):
    """A `pago` is written to the ledger.

    The customer owes 30,00 € — the `cargo` fixture — and pays exactly
    that. A payment without a debt behind it would be refused by rule 19:
    the bound is the customer's outstanding, and a customer who owes
    nothing may not pay 30,00 €.
    """
    respuesta = cliente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "30.00"},
        format="json",
    )

    assert respuesta.status_code == 201
    assert LedgerEntry.objects.filter(kind="pago").count() == 1


def test_the_ledger_may_not_carry_an_occurred_at(cliente, customer, cargo):
    """Rule 4: the server stamps the entry, never the client."""
    respuesta = cliente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "30.00", "occurred_at": "2026-05-01T10:00:00Z"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"
    assert LedgerEntry.objects.filter(kind="pago").count() == 0


def test_a_non_positive_amount_is_refused(cliente, customer):
    """PA-10: the amount must be greater than zero."""
    respuesta = cliente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "0.00"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "importe_no_positivo"
    assert LedgerEntry.objects.filter(kind="pago").count() == 0


def test_an_unknown_kind_is_refused(cliente, customer):
    """PA-10: the kind is `cargo` or `pago`, nothing else."""
    respuesta = cliente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "nota_credito", "amount": "10.00"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "tipo_desconocido"
    assert LedgerEntry.objects.filter(kind="pago").count() == 0


def test_a_charge_may_not_be_written_directly(cliente, customer):
    """The ledger accepts `kind` ∈ {`pago`} **only**.

    A `cargo` is written by the confirmation of a proposal, never directly:
    the charge exists only at the confirmation (ADR-19). This is the v2
    model in one assertion.
    """
    respuesta = cliente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "cargo", "amount": "30.00"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "tipo_desconocido"
    assert LedgerEntry.objects.filter(kind="cargo").count() == 0


def test_a_payment_larger_than_the_outstanding_is_refused(cliente, customer, cargo):
    """Rule 19: the excess is change, and it never enters the book.

    A client who hands over 35,00 € against a debt of 30,00 € is refused:
    the shop returns the excess as change and the owner records 30,00 €.
    There is no credit and no negative pending.
    """
    respuesta = cliente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "35.00"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "pago_excede_deuda"
    assert LedgerEntry.objects.filter(kind="pago").count() == 0


def test_a_payment_that_fits_is_recorded(cliente, customer, cargo):
    """A payment of exactly the debt is accepted."""
    respuesta = cliente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "30.00"},
        format="json",
    )

    assert respuesta.status_code == 201
    assert LedgerEntry.objects.filter(kind="pago").count() == 1


def test_the_dependiente_may_record_a_payment(tienda, helper, customer, cargo):
    """9.5: collecting is a counter act, and the `dependiente` collects.

    The credit book's POLICY stays the owner's - the `credit_limit`, the
    suspension and the credential - but the `dependiente` records the
    payments, because that is what the counter does.
    """
    api = APIClient()
    api.force_authenticate(helper)
    _sesion(api, tienda)

    respuesta = api.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "10.00"},
        format="json",
    )

    assert respuesta.status_code == 201
    assert LedgerEntry.objects.filter(kind="pago").count() == 1


def test_a_customer_of_another_shop_is_not_found(cliente, customer, tienda):
    """A customer of another shop answers 404, not 403.

    A 403 would confirm that the customer exists; a 404 says nothing.
    """
    otra = Shop.objects.create(name="Otra tienda", opening_cash=Decimal("0.00"))
    ajeno = Customer.objects.create(alias="Luis")
    Vinculo.objects.create(
        tienda=otra,
        cliente=ajeno,
        estado="aceptado",
    )

    respuesta = cliente.post(
        reverse("api:cliente_libreta", args=[ajeno.id]),
        {"kind": "pago", "amount": "10.00"},
        format="json",
    )

    assert respuesta.status_code == 404


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------


def test_the_catalogue_lists_the_active_products(cliente, producto):
    """PC-01: the catalogue exposes only the goods eligible for fiado."""
    Producto.objects.create(
        shop=producto.shop, nombre="Retirado", precio=Decimal("9.00"), activo=False
    )

    respuesta = cliente.get(reverse("api:catalogo"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [p["nombre"] for p in cuerpo] == ["Pan"]


def test_the_catalogue_carries_the_product_fields(cliente, producto):
    """PC-01: `nombre`, `precio`, `unidad` and `activo`.

    Plus the product's `id`: the proposal form has to name the product it
    is selling, and the id of a product of the OWNER's own catalogue is
    not a secret - it is not one of the nine staff-only fields.
    """
    respuesta = cliente.get(reverse("api:catalogo"))

    entrada = respuesta.json()[0]
    assert set(entrada) == {"activo", "id", "nombre", "precio", "unidad"}
    assert entrada["id"] == producto.id


def test_the_dependiente_may_not_read_the_catalogue(tienda, helper, producto):
    """PC-03: the catalogue is the owner's."""
    api = APIClient()
    api.force_authenticate(helper)
    _sesion(api, tienda)

    respuesta = api.get(reverse("api:catalogo"))

    assert respuesta.status_code == 403


def test_the_catalogue_price_is_a_default_and_not_a_constraint(cliente, producto):
    """PC-02: the owner may charge another amount, and the line keeps it.

    The catalogue holds the price of the moment; a line carries the price
    actually charged, as a snapshot. A later change to the catalogue never
    rewrites a stored line (IC-08).
    """
    from tienda.domain.charges import precio_unitario_de

    assert precio_unitario_de(Decimal("1.20"), Decimal("1.00")) == Decimal("1.00")
    assert precio_unitario_de(Decimal("1.20"), None) == Decimal("1.20")
