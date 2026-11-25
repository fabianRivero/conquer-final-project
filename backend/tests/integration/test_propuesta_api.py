"""The proposal, the shop's screen and the confirmation - tasks 5.1 to 5.7.

The heart of the v2 model: **the charge exists only at the confirmation**.

The client never writes to the ledger. The owner prepares a proposal with
its itemisation, the client confirms it on the shop's screen, and only then
does the charge exist and become debt. If the client declines, the owner
cancels the proposal and no debt remains.

The cases here are the ones the design fixes:

* preparing a proposal writes **no** charge and moves no balance - a
  proposal is a request, not a debt (CC-01);
* the itemisation is **mandatory**: the total equals the sum of the lines,
  and a proposal with no lines is refused with the same code (rule 3, IC-07);
* a product of another shop is refused (IC-07);
* the confirmation writes the charge, its lines **copied from the
  proposal's own lines**, and the confirmation - **in one transaction**
  (ADR-19, ADR-20);
* a second confirmation is refused and appends nothing (rule 7);
* a confirmation of a suspended customer writes **no** charge (rule 8);
* the cancellation writes **nothing** but the instant (CC-04);
* the screen carries the lines and the total and **nothing else** (CC-03,
  CAC-10);
* the origin is **inferred by the server**, never read from the body
  (rule 7b);
* the four proposal routes answer **403** to the `dependiente`, because the
  N5 gate is closed (5.6);
* two concurrent confirmations append exactly one charge (ADR-20, 5.7).

A note on how these tests assert. The Phase 4 slices found that a test
asserting a STATUS CODE can pass for the wrong reason - a pending view
answers 501 whatever the route does, so the assertion could not tell
"resolved" from "not resolved". Every assertion here that matters is on
the **effect**: the rows written, the rows NOT written, the state of the
proposal. The status code is a companion, never the proof.
"""

from __future__ import annotations

from tests.integration.personas import crear_persona


from decimal import Decimal
from threading import Barrier, Thread

import pytest

from tests.conftest import membresia
from django.contrib.auth.models import Group, User
from django.db import connections, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.models import (
    CargoLinea,
    Confirmacion,
    Customer,
    FiadoPropuesto,
    LedgerEntry,
    MiembroDeTienda,
    PerfilTienda,
    Producto,
    PropuestaLinea,
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
def helper(db, negocio):
    user = User.objects.create_user(username="dependiente", password="x")
    membresia(negocio, user, "dependiente")
    return user


@pytest.fixture
def otro_helper(db, negocio):
    """A second `dependiente` - the one whose proposals are not the first's."""
    user = User.objects.create_user(username="dependiente2", password="x")
    membresia(negocio, user, "dependiente")
    return user


@pytest.fixture
def tienda(db, negocio):
    """The shop of the credit book - the business's own shop."""
    return negocio.shop


def _api_de(user, tienda):
    """An API client whose session names the shop."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(user)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


@pytest.fixture
def api(owner, tienda):
    return _api_de(owner, tienda)


@pytest.fixture
def api_dependiente(helper, tienda):
    return _api_de(helper, tienda)


@pytest.fixture
def api_otro_dependiente(otro_helper, tienda):
    """A second `dependiente` - the one whose proposals are not the first's."""
    return _api_de(otro_helper, tienda)


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
def otra_tienda(db):
    return Shop.objects.create(
        name="Otra tienda", opening_cash=Decimal("0.00")
    )


@pytest.fixture
def producto(tienda):
    return Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )


@pytest.fixture
def producto_ajeno(otra_tienda):
    return Producto.objects.create(
        shop=otra_tienda, nombre="Leche", precio=Decimal("2.00"), unidad="unidad"
    )


def _lineas(producto, cantidad="3", precio=None):
    """The body of a proposal with one line."""
    precio = precio or str(producto.precio)
    return {
        "lineas": [
            {
                "producto_id": producto.id,
                "cantidad": cantidad,
                "precio_unitario": precio,
            }
        ],
        "total": str(Decimal(cantidad) * Decimal(precio)),
    }


def _preparar(api, customer, producto, **kwargs):
    """Prepare a proposal and return the response."""
    cuerpo = {"cliente_id": customer.id, **_lineas(producto, **kwargs)}
    return api.post(reverse("api:propuestas"), cuerpo, format="json")


# ---------------------------------------------------------------------------
# 5.1 - Preparing a proposal
# ---------------------------------------------------------------------------


def test_preparing_a_proposal_writes_no_charge(api, customer, producto):
    """CC-01: a proposal is a request, not a debt.

    While the proposal is pending it moves no balance: no `LedgerEntry`,
    no `CargoLinea`, no `Confirmacion`.
    """
    respuesta = _preparar(api, customer, producto)

    assert respuesta.status_code == 201
    assert LedgerEntry.objects.count() == 0
    assert CargoLinea.objects.count() == 0
    assert Confirmacion.objects.count() == 0


def test_preparing_a_proposal_moves_no_outstanding(api, customer, producto):
    """CC-01: the outstanding does not move at the preparation.

    The proposal is created - otherwise the assertion would be vacuous,
    because a route that does nothing also moves no outstanding. The
    companion test asserts that the proposal EXISTS, and this one asserts
    that the debt did not move; together they say what the test means.
    """
    from tienda.services import estado_de

    antes = estado_de(customer).total

    _preparar(api, customer, producto)

    # The proposal was created: the route works.
    assert FiadoPropuesto.objects.count() == 1
    # And the debt did not move.
    assert estado_de(customer).total == antes
    assert estado_de(customer).total == Decimal("0")


def test_a_proposal_is_stored_with_its_lines(api, customer, producto):
    """The proposal and its itemisation are stored."""
    respuesta = _preparar(api, customer, producto)

    assert respuesta.status_code == 201
    propuesta = FiadoPropuesto.objects.get()
    assert propuesta.estado == "pendiente"
    assert propuesta.total == Decimal("3.00")
    assert PropuestaLinea.objects.count() == 1
    linea = PropuestaLinea.objects.get()
    assert linea.cantidad == Decimal("3")
    assert linea.precio_unitario == Decimal("1.00")
    assert linea.total == Decimal("3.00")


def test_a_total_that_does_not_match_the_lines_is_refused(api, customer, producto):
    """Rule 3: the declared total equals the sum of the lines.

    The itemisation is mandatory, so a total that disagrees with its own
    lines is refused with `lineas_descuadradas`.
    """
    cuerpo = {"cliente_id": customer.id, **_lineas(producto)}
    cuerpo["total"] = "99.00"

    respuesta = api.post(reverse("api:propuestas"), cuerpo, format="json")

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "lineas_descuadradas"
    assert FiadoPropuesto.objects.count() == 0
    assert PropuestaLinea.objects.count() == 0


def test_a_proposal_with_no_lines_is_refused(api, customer):
    """Rule 3: a proposal with no lines is refused with the SAME code.

    A figure the client cannot see broken down is not a figure the client
    confirmed, so it cannot exist.
    """
    respuesta = api.post(
        reverse("api:propuestas"),
        {"cliente_id": customer.id, "lineas": []},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "lineas_descuadradas"
    assert FiadoPropuesto.objects.count() == 0


def test_a_product_of_another_shop_is_refused(api, customer, producto_ajeno):
    """IC-07: a product of another shop is refused."""
    respuesta = _preparar(api, customer, producto_ajeno)

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "producto_ajeno"
    assert FiadoPropuesto.objects.count() == 0


# ---------------------------------------------------------------------------
# 5.2 - The confirmation
# ---------------------------------------------------------------------------


def test_confirming_writes_the_charge_its_lines_and_the_confirmation(
    api, customer, producto
):
    """CC-01, ADR-19: the charge is born at the confirmation.

    The confirmation writes the `LedgerEntry(cargo)`, its `CargoLinea[]`
    **copied from the proposal's own lines**, and the `Confirmacion` - in
    one transaction.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 201

    cargo = LedgerEntry.objects.get()
    assert cargo.kind == "cargo"
    assert cargo.amount == Decimal("3.00")
    assert cargo.customer_id == customer.id

    lineas = CargoLinea.objects.all()
    assert lineas.count() == 1
    assert lineas[0].producto_id == producto.id
    assert lineas[0].cantidad == Decimal("3")
    assert lineas[0].precio_unitario == Decimal("1.00")
    assert lineas[0].total == Decimal("3.00")

    confirmacion = Confirmacion.objects.get()
    assert confirmacion.cargo_id == cargo.id
    assert confirmacion.estado == "confirmado"


def test_confirming_moves_the_outstanding_at_that_instant(api, customer, producto):
    """CC-01: the outstanding moves at the exact instant of the confirmation."""
    from tienda.services import estado_de

    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()
    assert estado_de(customer).total == Decimal("0")

    api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    assert estado_de(customer).total == Decimal("3.00")


def test_confirming_marks_the_proposal(api, customer, producto):
    """The proposal becomes `confirmado` and carries the instant."""
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    propuesta.refresh_from_db()
    assert propuesta.estado == "aceptado"
    assert propuesta.confirmed_at is not None
    assert propuesta.canceled_at is None


def test_a_second_confirmation_is_refused_and_appends_nothing(
    api, customer, producto
):
    """Rule 7: a proposal is confirmed once.

    The second confirmation is refused with `propuesta_ya_aceptada` and
    writes NOTHING - not a second charge, not a second confirmation.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )
    respuesta = api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "propuesta_ya_aceptada"
    assert LedgerEntry.objects.count() == 1
    assert CargoLinea.objects.count() == 1
    assert Confirmacion.objects.count() == 1


def test_confirming_a_suspended_customer_writes_no_charge(api, tienda, producto):
    """Rule 8: a proposal confirmed while the customer is suspended writes
    **no** charge.

    The suspension is DERIVED, never stored: the customer's outstanding
    already exceeds the limit.
    """
    from tienda.models import Customer as _Customer
    from tienda.models import Vinculo as _Vinculo

    cliente = crear_persona("beto", alias="Beto")[1]
    _Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("10.00"),
    )
    # A charge of 30,00 against a limit of 10,00: the derived state is
    # `suspendido` by `limite_superado`.
    LedgerEntry.objects.create(
        shop=tienda,
        customer=cliente,
        user=api.handler._force_user,
        kind="cargo",
        amount=Decimal("30.00"),
        occurred_at=timezone.now(),
    )

    _preparar(api, cliente, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] in ("limite_superado", "antiguedad_superada")
    assert LedgerEntry.objects.count() == 1  # only the pre-existing one
    assert CargoLinea.objects.count() == 0
    assert Confirmacion.objects.count() == 0

    propuesta.refresh_from_db()
    assert propuesta.estado == "pendiente"


# ---------------------------------------------------------------------------
# 5.3 - The cancellation
# ---------------------------------------------------------------------------


def test_cancelling_writes_nothing_but_the_instant(api, customer, producto):
    """CC-04: the cancellation writes nothing but the instant.

    No charge, no debt. The outstanding never moved, because it never moved
    in the first place.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api.post(
        reverse("api:propuesta_cancelar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 200
    assert LedgerEntry.objects.count() == 0
    assert CargoLinea.objects.count() == 0
    assert Confirmacion.objects.count() == 0

    propuesta.refresh_from_db()
    assert propuesta.estado == "rechazado"
    assert propuesta.canceled_at is not None
    assert propuesta.confirmed_at is None


def test_a_second_cancellation_is_refused(api, customer, producto):
    """Rule 7: a proposal is rejected once."""
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    api.post(
        reverse("api:propuesta_cancelar", args=[propuesta.id]), {}, format="json"
    )
    respuesta = api.post(
        reverse("api:propuesta_cancelar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "propuesta_ya_rechazada"


def test_a_rejected_proposal_never_becomes_a_charge(api, customer, producto):
    """CC-04, CC-01: the transition is one-way.

    A rejected proposal cannot be accepted afterwards, and the refusal
    writes nothing.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    api.post(
        reverse("api:propuesta_cancelar", args=[propuesta.id]), {}, format="json"
    )
    respuesta = api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "propuesta_ya_rechazada"
    assert LedgerEntry.objects.count() == 0
    assert Confirmacion.objects.count() == 0


# ---------------------------------------------------------------------------
# 5.4 - The screen
# ---------------------------------------------------------------------------


def test_the_screen_carries_the_lines_and_the_total(api, customer, producto):
    """CC-03: the screen shows the proposal's own lines and total.

    The formats are the ones the serializer declares: `cantidad` with
    three decimals and the money fields with two. A test that asserted
    `"3"` would be asserting a format the contract does not declare.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api.get(
        reverse("api:propuesta_pantalla", args=[propuesta.id])
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == "3.00"
    assert len(cuerpo["lineas"]) == 1
    assert cuerpo["lineas"][0]["cantidad"] == "3.000"
    assert cuerpo["lineas"][0]["precio_unitario"] == "1.00"
    assert cuerpo["lineas"][0]["total"] == "3.00"


def test_the_screen_carries_nothing_else(api, customer, producto):
    """CC-03, CAC-10: the screen carries the lines and the total and
    NOTHING ELSE.

    No balance, no ageing, no other customer, no `credit_limit`, no
    `codigo`. The screen is what the client reads at the counter.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api.get(
        reverse("api:propuesta_pantalla", args=[propuesta.id])
    )

    cuerpo = respuesta.json()
    assert set(cuerpo.keys()) == {"lineas", "total"}

    for linea in cuerpo["lineas"]:
        assert set(linea.keys()) == {"producto", "cantidad", "precio_unitario", "total"}


def test_the_screen_carries_no_credential(api, customer, producto):
    """CAC-10: no `codigo` reaches the screen."""
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api.get(
        reverse("api:propuesta_pantalla", args=[propuesta.id])
    )

    cuerpo = respuesta.json()
    assert "codigo" not in str(cuerpo)
    assert "prefix" not in str(cuerpo)
    assert "credit_limit" not in str(cuerpo)


def test_the_screen_of_another_shop_answers_404(api, customer, producto, otra_tienda):
    """CC-03: a proposal of another shop is not found.

    The shop comes from the session, so a proposal of another shop is
    simply not there - a 404, never a 403 that would leak its existence.

    **And the user has no role in the other shop**, so the permission
    refuses first: the role lives in the membership, and the membership
    names the shop. The screen is never even reached.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    api_otra = _api_de(api.handler._force_user, otra_tienda)
    respuesta = api_otra.get(
        reverse("api:propuesta_pantalla", args=[propuesta.id])
    )

    # The role is the membership's, and the membership names the shop:
    # the user has none in the other one, so the refusal comes first.
    assert respuesta.status_code == 403

    # And with a role IN that shop, the proposal is simply not there.
    otra = PerfilTienda.objects.create(
        user=api.handler._force_user, nombre="Otra tienda"
    )
    otra.shop = otra_tienda
    otra.save()
    membresia(otra, api.handler._force_user, "dueno")

    api_otra = _api_de(api.handler._force_user, otra_tienda)
    respuesta = api_otra.get(
        reverse("api:propuesta_pantalla", args=[propuesta.id])
    )

    assert respuesta.status_code == 404


# ---------------------------------------------------------------------------
# 5.5 - The server-inferred origin
# ---------------------------------------------------------------------------


def test_the_origin_is_inferred_from_the_session(api, customer, producto):
    """Rule 7b: the origin comes from the acting session.

    The `dueno` prepares it, so `origen='tienda'` and `confirmado_por` is
    the owner. Neither is read from the body.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    confirmacion = Confirmacion.objects.get()
    assert confirmacion.origen == "tienda"
    assert confirmacion.confirmado_por_id == propuesta.user_id


def test_the_origin_is_never_read_from_the_body(api, customer, producto):
    """Rule 7b: the body cannot name the origin nor the facilitator.

    The body of the confirmation is `{}` - the route admits no field at
    all. A request that names the origin is refused on the **presence** of
    the field, exactly like `occurred_at` on the cash movement, and
    nothing is written.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]),
        {"origen": "facilitado", "facilitado_por": 999},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"
    assert LedgerEntry.objects.count() == 0
    assert Confirmacion.objects.count() == 0


def test_the_origin_follows_the_acting_session(api, customer, producto):
    """Rule 7b: the origin follows the acting session.

    The gate is OPEN, so the `dependiente` may confirm. What this test
    pins is the INFERENCE: the origin is derived from the acting session
    and from nothing else, and the actor is named either way.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    confirmacion = Confirmacion.objects.get()
    assert confirmacion.origen == "tienda"
    assert confirmacion.confirmado_por_id == propuesta.user_id


def test_a_facilitator_outside_the_shop_is_refused(api, customer, producto, tienda):
    """Rule 7b: a `facilitado_por` outside the shop is refused.

    The body field is not admitted at all, so the refusal is
    `campo_no_admitido` - the request never reaches the write.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    otro = User.objects.create_user(username="ajeno", password="x")
    respuesta = api.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]),
        {"facilitado_por": otro.id},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"
    assert LedgerEntry.objects.count() == 0


# ---------------------------------------------------------------------------
# 5.6 - The N5 gate
# ---------------------------------------------------------------------------


def test_the_dependiente_may_prepare_a_proposal(api_dependiente, customer, producto):
    """9.1: the gate is OPEN, so the `dependiente` prepares.

    The capability table marks the four proposal routes with `*(N5)*` for
    the `dependiente`, and the owner has opened the gate. The proposal
    exists and it names **its** preparer - which is also the ownership:
    the `dependiente` confirms only its own.
    """
    respuesta = _preparar(api_dependiente, customer, producto)

    assert respuesta.status_code == 201
    propuesta = FiadoPropuesto.objects.get()
    assert propuesta.user_id == api_dependiente.handler._force_user.id
    assert propuesta.estado == "pendiente"


def test_the_dependiente_may_see_the_screen(api, api_dependiente, customer, producto):
    """9.1: the `dependiente` reads the screen of **its own** proposal."""
    _preparar(api_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api_dependiente.get(
        reverse("api:propuesta_pantalla", args=[propuesta.id])
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == "3.00"


def test_the_dependiente_may_confirm(api_dependiente, customer, producto):
    """9.1: the `dependiente` confirms the proposal it prepared."""
    _preparar(api_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api_dependiente.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 201
    assert LedgerEntry.objects.count() == 1
    assert Confirmacion.objects.count() == 1


def test_the_dependiente_may_reject(api_dependiente, customer, producto):
    """9.1: the `dependiente` cancels its own proposal."""
    _preparar(api_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api_dependiente.post(
        reverse("api:propuesta_cancelar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 200
    propuesta.refresh_from_db()
    assert propuesta.estado == "rechazado"
    assert LedgerEntry.objects.count() == 0


def test_the_dependiente_reaches_only_its_own_proposals(
    api_dependiente, api_otro_dependiente, customer, producto
):
    """9.2: the ownership. Each one confirms only what it prepared.

    The refusal is **404**, not 403: a 403 would confirm that the
    proposal exists. The gate opened the ROUTE; the ownership filter
    guards the OBJECT.
    """
    _preparar(api_otro_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api_dependiente.post(
        reverse("api:propuesta_confirmar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 404
    assert LedgerEntry.objects.count() == 0


# ---------------------------------------------------------------------------
# 5.7 - The concurrency
# ---------------------------------------------------------------------------


@pytest.fixture
def api_con_sesion(owner, tienda):
    """A client that carries BOTH the authentication and the shop scope.

    The concurrency tests need a client that is indistinguishable from a
    real staff session: `force_authenticate` alone is not enough, because
    the staff scope lives in `session["shop_id"]` and a request without it
    is refused with 403. The threads below build their own clients from
    this fixture's session, and they need the same one.
    """
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(owner)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api, sesion.session_key


def _api_con_la_sesion(user, session_key):
    """A fresh client carrying the given session.

    A thread cannot share the `APIClient` of the main thread safely, so
    each one builds its own - with the same session key, so it is the
    same staff scope.
    """
    api = APIClient()
    api.force_authenticate(user)
    api.cookies["sessionid"] = session_key
    return api


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_confirmations_append_one_charge(
    api_con_sesion, customer, producto
):
    """ADR-20: one charge per confirmed proposal.

    Two threads confirm the SAME proposal at the same time. Exactly one
    `Confirmacion` and exactly one `cargo` must exist afterwards.

    The threads are real threads against real PostgreSQL: the row lock of
    `select_for_update()` is what makes the second one read the state the
    first wrote.

    **Why `transaction=True`.** The staff scope lives in the session row,
    and that row is written inside the transaction that wraps the test. A
    thread opens its own connection, and that connection cannot see an
    uncommitted row - so the thread would be refused with 403 for having
    no shop scope, and the test would prove nothing. Without the wrapping
    transaction the session row is committed and the thread reads it.
    The cost is that the test does not roll itself back; PostgreSQL's
    test database is truncated between tests instead.
    """
    api, session_key = api_con_sesion
    _preparar(api, customer, producto)
    propuesta_id = FiadoPropuesto.objects.get().id

    barrera = Barrier(2)
    respuestas = []

    def confirmar():
        api_local = _api_con_la_sesion(api.handler._force_user, session_key)
        barrera.wait()
        respuestas.append(
            api_local.post(
                reverse("api:propuesta_confirmar", args=[propuesta_id]),
                {},
                format="json",
            )
        )

    hilos = [Thread(target=confirmar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert Confirmacion.objects.count() == 1
    assert LedgerEntry.objects.count() == 1
    assert CargoLinea.objects.count() == 1

    propuesta = FiadoPropuesto.objects.get()
    assert propuesta.estado == "aceptado"

    # One of the two was refused, and it was refused with the code of the
    # one-way transition - never with a 500.
    codigos = sorted(r.status_code for r in respuestas)
    assert codigos == [201, 422]
    refute = [r for r in respuestas if r.status_code == 422][0]
    assert refute.json()["codigo_error"] == "propuesta_ya_aceptada"


@pytest.mark.django_db(transaction=True)
def test_a_confirmation_racing_a_cancellation_leaves_one_state(
    api_con_sesion, customer, producto
):
    """5.7: the proposal ends in exactly one state.

    A confirmation racing a cancellation must never leave the proposal
    both accepted and rejected, nor a charge without its confirmation.
    The `transaction=True` is for the same reason as the test above.
    """
    api, session_key = api_con_sesion
    _preparar(api, customer, producto)
    propuesta_id = FiadoPropuesto.objects.get().id

    barrera = Barrier(2)
    respuestas = []

    def confirmar():
        api_local = _api_con_la_sesion(api.handler._force_user, session_key)
        barrera.wait()
        respuestas.append(
            api_local.post(
                reverse("api:propuesta_confirmar", args=[propuesta_id]),
                {},
                format="json",
            )
        )

    def cancelar():
        api_local = _api_con_la_sesion(api.handler._force_user, session_key)
        barrera.wait()
        respuestas.append(
            api_local.post(
                reverse("api:propuesta_cancelar", args=[propuesta_id]),
                {},
                format="json",
            )
        )

    hilos = [Thread(target=confirmar), Thread(target=cancelar)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    propuesta = FiadoPropuesto.objects.get()
    assert propuesta.estado in ("aceptado", "rechazado")
    assert not (propuesta.confirmed_at and propuesta.canceled_at)

    # A charge and its confirmation always come together.
    assert Confirmacion.objects.count() == LedgerEntry.objects.count()
    # And no request ended in a 500.
    assert all(r.status_code < 500 for r in respuestas)
