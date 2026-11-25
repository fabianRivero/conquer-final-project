"""The proposed payment - tasks 6.4, 6.5 and 6.6.

A `PagoPropuesto` is a **request, not a scope**. It creates no ledger row,
it moves no balance, and it grants the client nothing beyond the
acknowledgement that it was received. The `pago` itself is a separate
`LedgerEntry` appended by the owner, so the credit book stays append-only
even though the request that preceded it is not.

The cases, and where each comes from:

* the proposal writes **no ledger row** (CC-07, PA-09);
* a non-positive `importe` is refused (`importe_no_positivo`, rule 17);
* **the proposal names NO charge**: the body carries `importe` and
  `referencia` only, and a body carrying a `cargo_id` is refused
  (PA-02, ADR-27);
* the owner's validation appends a `LedgerEntry(pago)` whose amount is
  **exactly** the proposal's `importe` - never recomputed, never rounded
  - plus its `ImputacionPago` rows, one per charge the payment retires,
  FIFO by charge (PA-09, ADR-27);
* a second validation is refused (`pago_ya_resuelto`) and appends no
  second `pago`;
* `rechazar` moves the proposal to `rechazado` and writes no `pago`;
* rule 19: a proposed amount larger than the customer's outstanding is
  refused with `pago_excede_deuda`, writes no `pago` and leaves the
  proposal `pendiente` - the owner rejects it and returns the excess as
  change (ADR-26);
* a proposed payment grants no read of the credit book and no further
  write (CAC-03, CAC-10).
"""


from __future__ import annotations

from tests.integration.personas import crear_persona

from decimal import Decimal

import pytest

from tests.conftest import membresia
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.models import (
    CargoLinea,
    Confirmacion,
    Customer,
    FiadoPropuesto,
    ImputacionPago,
    LedgerEntry,
    PagoPropuesto,
    Producto,
    Shop,
    Vinculo,
)

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
def tienda(db, negocio):
    """The shop of the credit book - the business's own shop."""
    return negocio.shop


@pytest.fixture
def customer(tienda):
    """A person, and the LINK that says she is a trusted client of the shop."""
    cliente_usuario, cliente = crear_persona("ana", alias="Ana")
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
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )


@pytest.fixture
def persona(db, tienda, customer, owner):
    """**La persona, con su cuenta.**

    La credencial se fue en el 10.6: la persona propone el pago desde
    SU cuenta, con la sesion de la persona y el `shop_id` ausente.

    **Es la MISMA persona que `customer`** - la ficha y la cuenta son la
    misma persona, y una prueba que las tratara como dos distintos
    probaria el caso equivocado.
    """
    return customer.user


@pytest.fixture
def api_cliente():
    """A client with the PERSON's session.

    **The credential is gone**: the person's own session is the door, and
    it carries no `shop_id` - a person is not in a shop.
    """

    def _api(usuario):
        from django.contrib.sessions.backends.db import SessionStore

        api = APIClient()
        api.force_authenticate(usuario)
        sesion = SessionStore()
        sesion.save()
        api.cookies["sessionid"] = sesion.session_key
        return api

    return _api


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


def _cargo(tienda, customer, owner, producto, *, importe="8.00", when=None):
    momento = when or timezone.now()
    cargo = LedgerEntry.objects.create(
        shop=tienda,
        customer=customer,
        user=owner,
        kind="cargo",
        amount=Decimal(importe),
        occurred_at=momento,
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
        confirmado_en=momento,
        origen="tienda",
        confirmado_por=owner,
    )
    return cargo


# ---------------------------------------------------------------------------
# 6.4 - The client proposes a payment
# ---------------------------------------------------------------------------


def test_a_proposed_payment_creates_no_ledger_row(
    api_cliente, persona, tienda, customer, owner, producto
):
    """CC-07, PA-09: the proposal writes NOTHING to the book.

    The `pago` is a separate `LedgerEntry` appended by the OWNER. The
    book stays append-only even though the request that preceded it is
    not.
    """
    _cargo(tienda, customer, owner, producto)

    respuesta = api_cliente(persona).post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00", "referencia": "billete"},
        format="json",
    )

    assert respuesta.status_code == 201
    propuesta = PagoPropuesto.objects.get()
    assert propuesta.estado == "pendiente"
    assert propuesta.importe == Decimal("5.00")
    assert propuesta.customer_id == customer.id

    assert LedgerEntry.objects.count() == 1  # only the charge
    assert ImputacionPago.objects.count() == 0


def test_a_non_positive_amount_is_refused(api_cliente, persona, customer):
    """Rule 17: the amount must be greater than zero."""
    respuesta = api_cliente(persona).post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "0.00"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "importe_no_positivo"
    assert PagoPropuesto.objects.count() == 0


def test_the_proposal_names_no_charge(api_cliente, persona, tienda, customer, owner, producto):
    """PA-02, ADR-27: the client does not choose which debt it pays.

    The body carries `importe` and `referencia` only. A body that names a
    charge is refused on the **presence** of the field.
    """
    cargo = _cargo(tienda, customer, owner, producto)

    respuesta = api_cliente(persona).post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "5.00", "cargo_id": cargo.id},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"
    assert PagoPropuesto.objects.count() == 0


# ---------------------------------------------------------------------------
# 6.5 - The owner validates the payment
# ---------------------------------------------------------------------------


def test_validating_appends_the_pago_and_its_imputations(
    api_cliente, api_dueno, persona, tienda, customer, owner, producto
):
    """PA-09, ADR-27: the validation appends the `pago` and its repartition.

    The amount is **exactly** the proposal's `importe` - never recomputed,
    never rounded - and the `ImputacionPago` rows are one per charge the
    payment retires, FIFO by charge.
    """
    # The charges are stamped in the PAST, and the second one is OLDER
    # than the first by nothing at all - the FIFO retires them in the
    # order they were written. A charge in the future is not part of the
    # outstanding at the payment's instant, and the server never stamps
    # one.
    _cargo(
        tienda,
        customer,
        owner,
        producto,
        importe="8.00",
        when=timezone.now() - timezone.timedelta(minutes=2),
    )
    _cargo(
        tienda,
        customer,
        owner,
        producto,
        importe="7.00",
        when=timezone.now() - timezone.timedelta(minutes=1),
    )

    api_cliente(persona).post(
        reverse("api:cuenta_pagos_proponer"),
        {"importe": "10.00"},
        format="json",
    )
    propuesta = PagoPropuesto.objects.get()

    respuesta = api_dueno.post(
        reverse("api:pago_validar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 201

    pago = LedgerEntry.objects.get(kind="pago")
    assert pago.amount == Decimal("10.00")
    assert pago.customer_id == customer.id

    # One imputation per charge it retires, FIFO by charge.
    imputaciones = ImputacionPago.objects.filter(pago=pago).order_by("id")
    assert imputaciones.count() == 2
    assert imputaciones[0].importe == Decimal("8.00")
    assert imputaciones[1].importe == Decimal("2.00")

    propuesta.refresh_from_db()
    assert propuesta.estado == "validado"
    assert propuesta.resolved_at is not None
    assert propuesta.resolved_by_id == owner.id


def test_a_second_validation_is_refused_and_appends_nothing(
    api_cliente, api_dueno, persona, tienda, customer, owner, producto
):
    """Rule 18: a proposed payment is resolved once."""
    _cargo(tienda, customer, owner, producto)

    api_cliente(persona).post(
        reverse("api:cuenta_pagos_proponer"), {"importe": "5.00"}, format="json"
    )
    propuesta = PagoPropuesto.objects.get()

    api_dueno.post(
        reverse("api:pago_validar", args=[propuesta.id]), {}, format="json"
    )
    respuesta = api_dueno.post(
        reverse("api:pago_validar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "pago_ya_resuelto"
    assert LedgerEntry.objects.filter(kind="pago").count() == 1


def test_rejecting_writes_no_pago(api_cliente, api_dueno, persona, tienda, customer, owner, producto):
    """CC-07: the rejection writes no `pago`."""
    _cargo(tienda, customer, owner, producto)

    api_cliente(persona).post(
        reverse("api:cuenta_pagos_proponer"), {"importe": "5.00"}, format="json"
    )
    propuesta = PagoPropuesto.objects.get()

    respuesta = api_dueno.post(
        reverse("api:pago_rechazar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 200
    assert LedgerEntry.objects.filter(kind="pago").count() == 0
    propuesta.refresh_from_db()
    assert propuesta.estado == "rechazado"
    assert propuesta.resolved_at is not None


def test_an_amount_larger_than_the_outstanding_is_refused(
    api_cliente, api_dueno, persona, tienda, customer, owner, producto
):
    """Rule 19, ADR-26: the excess is change and it never enters the book.

    A proposed amount larger than the customer's outstanding is refused
    with `pago_excede_deuda`, writes NO `pago`, and leaves the proposal
    `pendiente` - the owner rejects it and returns the excess as change.
    """
    _cargo(tienda, customer, owner, producto, importe="8.00")

    api_cliente(persona).post(
        reverse("api:cuenta_pagos_proponer"), {"importe": "20.00"}, format="json"
    )
    propuesta = PagoPropuesto.objects.get()

    respuesta = api_dueno.post(
        reverse("api:pago_validar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "pago_excede_deuda"
    assert LedgerEntry.objects.filter(kind="pago").count() == 0
    assert ImputacionPago.objects.count() == 0

    propuesta.refresh_from_db()
    assert propuesta.estado == "pendiente"
    assert propuesta.resolved_at is None


# ---------------------------------------------------------------------------
# 6.6 - A proposed payment is not a scope
# ---------------------------------------------------------------------------


def test_a_proposed_payment_grants_no_read_of_the_credit_book(
    api_cliente, persona, tienda, customer, owner, producto
):
    """CAC-03, CAC-10: the proposal grants nothing.

    Having proposed a payment grants no read of the credit book and no
    read of another customer's data. The person's scope is exactly her
    own routes.
    """
    valor = persona
    cargo = _cargo(tienda, customer, owner, producto)

    api = api_cliente(valor)
    api.post(
        reverse("api:cuenta_pagos_proponer"), {"importe": "5.00"}, format="json"
    )

    # The owner's routes are not reachable with a person's session.
    for ruta in (reverse("api:clientes"), reverse("api:posicion")):
        respuesta = api.get(ruta)
        assert respuesta.status_code == 403

    # And her own charges ARE reachable - through HER route.
    assert api.get(reverse("api:cuenta_cargos")).status_code == 200


def test_the_client_cannot_validate_its_own_proposal(
    api_cliente, persona, tienda, customer, owner, producto
):
    """The client proposes; the OWNER validates.

    A client request to the owner's validation route is refused.
    """
    _cargo(tienda, customer, owner, producto)

    api_cliente(persona).post(
        reverse("api:cuenta_pagos_proponer"), {"importe": "5.00"}, format="json"
    )
    propuesta = PagoPropuesto.objects.get()

    respuesta = api_cliente(persona).post(
        reverse("api:pago_validar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 403
    assert LedgerEntry.objects.filter(kind="pago").count() == 0
