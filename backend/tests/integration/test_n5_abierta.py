"""Phase 9 - the N5 gate is OPEN: the `dependiente` operates the counter.

The N5 gate is a **decision**, not a feature flag: it was closed while the
validation round with the shop owners had not been run, and the owner has
now decided that the `dependiente` prepares, confirms and collects.

The decision is a **product decision under a declared hypothesis**, not
field evidence - the project's `knowledge_basis` stays `design-hypothesis`
and says so.

What the decision is, and what it is not:

* the `dependiente` **prepares** a proposal, and **confirms** and
  **cancels** it - but **only the proposals it prepared**. Each one owns
  its own fiados; nobody confirms somebody else's;
* the `dependiente` **reads the credit book** and **records a payment**
  on **any** debt of the shop - including a debt whose charge the owner
  confirmed. Collecting is a counter act, not a personal one;
* the `dependiente` does **not** set the `credit_limit`, does **not**
  lift a suspension, does **not** issue or rotate a `codigo`, and does
  **not** read the catalogue. Those stay the owner's.

The reduced schema is the boundary: the `dependiente` sees the debts and
none of the owner's policy fields. A field that is not declared cannot
appear whatever the query returns.

Every assertion here is on the **effect** - the rows written, the rows NOT
written, the fields present and absent - never on a status code alone.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

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
def owner(db):
    user = User.objects.create_user(username="dueno", password="x")
    user.groups.add(Group.objects.create(name="dueno"))
    return user


@pytest.fixture
def helper(db):
    user = User.objects.create_user(username="dependiente", password="x")
    user.groups.add(Group.objects.get_or_create(name="dependiente")[0])
    return user


@pytest.fixture
def otro_helper(db):
    """A second `dependiente` - the one whose proposals are not the first's."""
    user = User.objects.create_user(username="dependiente2", password="x")
    user.groups.add(Group.objects.get_or_create(name="dependiente")[0])
    return user


@pytest.fixture
def tienda(db):
    return Shop.objects.create(
        name="Tienda de prueba", opening_cash=Decimal("150.00")
    )


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
    return _api_de(otro_helper, tienda)


@pytest.fixture
def customer(tienda):
    return Customer.objects.create(
        shop=tienda, alias="Ana", credit_limit=Decimal("100.00")
    )


@pytest.fixture
def producto(tienda):
    return Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )


def _lineas(producto, cantidad="3", precio=None):
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
    cuerpo = {"cliente_id": customer.id, **_lineas(producto, **kwargs)}
    return api.post(reverse("api:propuestas"), cuerpo, format="json")


def _confirmar(api, propuesta_id):
    return api.post(
        reverse("api:propuesta_confirmar", args=[propuesta_id]), {}, format="json"
    )


# ---------------------------------------------------------------------------
# 9.1 - The gate is open: the `dependiente` prepares
# ---------------------------------------------------------------------------


def test_el_dependiente_prepara_un_fiado(api_dependiente, customer, producto):
    """The gate is OPEN: the `dependiente` prepares a proposal.

    The proposal exists, and it names **its** preparer. Nothing is
    written to the book: a proposal is a request, not a debt.
    """
    respuesta = _preparar(api_dependiente, customer, producto)

    assert respuesta.status_code == 201
    propuesta = FiadoPropuesto.objects.get()
    assert propuesta.user_id == api_dependiente.handler._force_user.id
    assert propuesta.estado == "pendiente"
    # And no debt was born.
    assert LedgerEntry.objects.count() == 0
    assert Confirmacion.objects.count() == 0


def test_el_dependiente_confirma_su_propia_propuesta(api_dependiente, customer, producto):
    """The `dependiente` confirms the proposal it prepared.

    The charge is born at the confirmation, exactly as it is for the
    owner: the rule is one rule, not two.
    """
    _preparar(api_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = _confirmar(api_dependiente, propuesta.id)

    assert respuesta.status_code == 201
    assert LedgerEntry.objects.count() == 1
    cargo = LedgerEntry.objects.get()
    assert cargo.kind == "cargo"
    assert cargo.amount == Decimal("3.00")
    assert Confirmacion.objects.count() == 1


def test_el_dependiente_cancela_su_propia_propuesta(api_dependiente, customer, producto):
    """The `dependiente` cancels its own proposal.

    The cancellation writes **nothing** but the instant: no charge, no
    lines, no confirmation.
    """
    _preparar(api_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api_dependiente.post(
        reverse("api:propuesta_cancelar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 200
    propuesta.refresh_from_db()
    assert propuesta.estado == "cancelado"
    assert LedgerEntry.objects.count() == 0


def test_el_dependiente_ve_la_pantalla_de_su_propuesta(api_dependiente, customer, producto):
    """The `dependiente` reads the screen of its own proposal."""
    _preparar(api_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api_dependiente.get(
        reverse("api:propuesta_pantalla", args=[propuesta.id])
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == "3.00"


# ---------------------------------------------------------------------------
# 9.2 - The ownership: each one confirms only its own
# ---------------------------------------------------------------------------


def test_el_dependiente_no_confirma_la_propuesta_de_otro(
    api_dependiente, api_otro_dependiente, customer, producto
):
    """Each one owns its own fiados: nobody confirms somebody else's.

    The answer is **404**, not 403: a 403 would confirm that the
    proposal exists. The gate is open - the route does not refuse the
    role, it refuses the **object**.
    """
    _preparar(api_otro_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = _confirmar(api_dependiente, propuesta.id)

    assert respuesta.status_code == 404
    assert LedgerEntry.objects.count() == 0
    assert Confirmacion.objects.count() == 0


def test_el_dependiente_no_ve_la_pantalla_de_otro(
    api_dependiente, api_otro_dependiente, customer, producto
):
    """The screen of somebody else's proposal is NOT FOUND."""
    _preparar(api_otro_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api_dependiente.get(
        reverse("api:propuesta_pantalla", args=[propuesta.id])
    )

    assert respuesta.status_code == 404


def test_el_dependiente_no_cancela_la_propuesta_de_otro(
    api_dependiente, api_otro_dependiente, customer, producto
):
    """The cancellation of somebody else's proposal is NOT FOUND."""
    _preparar(api_otro_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = api_dependiente.post(
        reverse("api:propuesta_cancelar", args=[propuesta.id]), {}, format="json"
    )

    assert respuesta.status_code == 404
    propuesta.refresh_from_db()
    assert propuesta.estado == "pendiente"


def test_el_dueno_confirma_su_propia_propuesta(api, api_dependiente, customer, producto):
    """The owner confirms its own proposal - the rule is symmetric.

    The `dependiente` does not reach it: the same ownership filter that
    protects one `dependiente` from another protects the owner from the
    `dependiente`.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    respuesta = _confirmar(api_dependiente, propuesta.id)

    assert respuesta.status_code == 404
    assert LedgerEntry.objects.count() == 0


# ---------------------------------------------------------------------------
# 9.3 - The origin and who confirmed
# ---------------------------------------------------------------------------


def test_la_confirmacion_del_dependiente_dice_quien_confirmo(
    api_dependiente, customer, producto
):
    """`confirmado_por` names the actor, ALWAYS.

    The origin says **what kind of act** it was - `tienda` or
    `dependiente` - and `confirmado_por` says **who** did it. There is
    no case in which the name is missing.
    """
    _preparar(api_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    _confirmar(api_dependiente, propuesta.id)

    confirmacion = Confirmacion.objects.get()
    assert confirmacion.origen == "dependiente"
    assert confirmacion.confirmado_por_id is not None
    assert confirmacion.confirmado_por_id == propuesta.user_id


def test_la_confirmacion_del_dueno_dice_quien_confirmo(api, customer, producto):
    """The owner's confirmation says `tienda` and names the owner."""
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()

    _confirmar(api, propuesta.id)

    confirmacion = Confirmacion.objects.get()
    assert confirmacion.origen == "tienda"
    assert confirmacion.confirmado_por_id == propuesta.user_id


def test_ninguna_confirmacion_carece_de_actor(api, api_dependiente, customer, producto):
    """No confirmation ever lacks its actor - neither role's.

    The two assertions together say what the test means: the field is
    filled by the code, and it is filled by the **same** code for both
    roles.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()
    _confirmar(api, propuesta.id)

    _preparar(api_dependiente, customer, producto, cantidad="2")
    segunda = FiadoPropuesto.objects.order_by("-id").first()
    _confirmar(api_dependiente, segunda.id)

    confirmaciones = Confirmacion.objects.all()
    assert confirmaciones.count() == 2
    for confirmacion in confirmaciones:
        assert confirmacion.confirmado_por_id is not None


# ---------------------------------------------------------------------------
# 9.4 - The credit book: what the `dependiente` reads
# ---------------------------------------------------------------------------


def test_el_dependiente_ve_las_deudas_del_cliente(api_dependiente, customer, producto):
    """The `dependiente` reads the debts of the shop's customers.

    It is a counter act to collect a debt, and collecting needs to see
    the debt. The schema declares the debts and nothing of the owner's
    policy.
    """
    _preparar(api_dependiente, customer, producto)
    propuesta = FiadoPropuesto.objects.get()
    _confirmar(api_dependiente, propuesta.id)

    respuesta = api_dependiente.get(reverse("api:clientes"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo) == 1
    fila = cuerpo[0]
    assert fila["alias"] == "Ana"
    # The debts are there: the charge's amount and what is paid.
    assert Decimal(str(fila["pendiente"])) == Decimal("3.00")


def test_el_dependiente_no_ve_la_politica_del_dueno(
    api_dependiente, customer, producto, owner
):
    """The reduced schema declares NONE of the owner's policy fields.

    No `credit_limit`, no ageing, no `codigo`, no prefix. The reduced
    payload is not the full one with fields removed: it is a different
    schema, so a field that is not declared cannot appear whatever the
    query returns.
    """
    CustomerCodigo.objects.create(
        shop=customer.shop,
        customer=customer,
        prefix="ABCDEF",
        codigo_hash="x" * 40,
        issued_at=timezone.now(),
        issued_by=owner,
    )

    respuesta = api_dependiente.get(reverse("api:clientes"))

    assert respuesta.status_code == 200
    fila = respuesta.json()[0]
    for prohibido in (
        "credit_limit",
        "antiguedad_max_dias",
        "suspended_reason",
        "codigo",
        "prefix",
        "issued_at",
    ):
        assert prohibido not in fila, f"el dependiente ve {prohibido}"


def test_el_dueno_sigue_veiendo_el_schema_completo(api, customer, producto):
    """The owner's schema is unchanged: this decision did not shrink it.

    The companion of the reduced schema: without it, "the `dependiente`
    sees less" would pass on a schema that sees nothing at all.
    """
    respuesta = api.get(reverse("api:clientes"))

    assert respuesta.status_code == 200
    fila = respuesta.json()[0]
    assert "credit_limit" in fila
    assert Decimal(str(fila["credit_limit"])) == Decimal("100.00")


def test_el_dependiente_no_ve_el_catalogo(api_dependiente, tienda):
    """The catalogue stays the owner's: it is not a counter act."""
    Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )

    respuesta = api_dependiente.get(reverse("api:catalogo"))

    assert respuesta.status_code == 403


# ---------------------------------------------------------------------------
# 9.5 - The payment: anybody collects
# ---------------------------------------------------------------------------


def test_el_dependiente_registra_un_pago(api, api_dependiente, customer, producto):
    """The `dependiente` records a payment on ANY debt of the shop.

    Collecting is a counter act. The debt may have been born from the
    owner's own proposal - and the payment is still recorded.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()
    _confirmar(api, propuesta.id)

    respuesta = api_dependiente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "3.00"},
        format="json",
    )

    assert respuesta.status_code == 201
    pago = LedgerEntry.objects.get(kind="pago")
    assert pago.amount == Decimal("3.00")
    assert pago.user_id == api_dependiente.handler._force_user.id


def test_el_pago_del_dependiente_respeta_la_regla_19(
    api, api_dependiente, customer, producto
):
    """The `dependiente` is subject to rule 19 like everybody else.

    A payment larger than the outstanding is refused, and it writes
    nothing: the excess is change and never enters the book.
    """
    _preparar(api, customer, producto)
    propuesta = FiadoPropuesto.objects.get()
    _confirmar(api, propuesta.id)

    respuesta = api_dependiente.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "10.00"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "pago_excede_deuda"
    assert LedgerEntry.objects.filter(kind="pago").count() == 0


# ---------------------------------------------------------------------------
# 9.6 - What stays the owner's
# ---------------------------------------------------------------------------


def test_el_dependiente_no_crea_clientes(api_dependiente):
    """Creating a customer is the owner's: it is the credit policy."""
    respuesta = api_dependiente.post(
        reverse("api:clientes"), {"alias": "Bruno"}, format="json"
    )

    assert respuesta.status_code == 403
    assert Customer.objects.count() == 0


def test_el_dependiente_no_ponde_el_credit_limit(api_dependiente, customer):
    """The `credit_limit` is the owner's policy, and it stays his."""
    respuesta = api_dependiente.patch(
        reverse("api:cliente_detalle", args=[customer.id]),
        {"credit_limit": "500.00"},
        format="json",
    )

    assert respuesta.status_code == 403
    customer.refresh_from_db()
    assert customer.credit_limit == Decimal("100.00")


def test_el_dependiente_no_emite_el_codigo(api_dependiente, customer):
    """The credential is the owner's: it opens the client's own scope.

    The route is a **pending view** - it answers 501 for everybody,
    because the issuing of a `codigo` was never built. The guarantee
    here is therefore not "the `dependiente` is refused" but "the route
    is the owner's alone": the credential table is written by the owner,
    and the `dependiente` writes no credential row.

    The companion is the `test_no_leak` suite, which walks the whole
    tree looking for the credential - a `dependiente` request that
    created a `CustomerCodigo` would be found there.
    """
    respuesta = api_dependiente.post(
        reverse("api:cliente_codigo", args=[customer.id]), {}, format="json"
    )

    # The route is not built for anybody: no credential is issued.
    assert respuesta.status_code == 501
    assert CustomerCodigo.objects.count() == 0


# ---------------------------------------------------------------------------
# 9.7 - Several fiados at once
# ---------------------------------------------------------------------------


def test_un_cliente_puede_tener_varias_compras_fiadas(api, customer, producto):
    """A customer may have SEVERAL pending fiados at once.

    The index that allowed one pending proposal per customer is gone:
    the client buys on credit more than once, and each proposal is its
    own purchase.
    """
    primera = _preparar(api, customer, producto, cantidad="2")
    segunda = _preparar(api, customer, producto, cantidad="3")

    assert primera.status_code == 201
    assert segunda.status_code == 201
    assert FiadoPropuesto.objects.count() == 2


def test_cada_propuesta_es_una_compra_distinta(api, customer, producto):
    """Two pending proposals of one customer are two charges, not one."""
    _preparar(api, customer, producto, cantidad="2")
    _preparar(api, customer, producto, cantidad="3")

    for propuesta in FiadoPropuesto.objects.all():
        _confirmar(api, propuesta.id)

    assert LedgerEntry.objects.filter(kind="cargo").count() == 2
    assert CargoLinea.objects.count() == 2
    assert Confirmacion.objects.count() == 2
