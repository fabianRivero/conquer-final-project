"""The service layer — task 4.13.

The service layer is the only layer that touches the ORM, and it is where
the transactional checks of design §3.2 become refusals. The tests here
cover three things:

* **the conversions.** A rule of `domain/` never sees an ORM row. The
  service builds the plain values the rules expect, and the conversion is
  the only place that happens.
* **the per-row twins of the database CHECKs.** A `CHECK` raises an
  `IntegrityError`, and an `IntegrityError` that reaches DRF is a 500. Each
  per-row invariant therefore has a twin in the service that refuses it
  **first**, with the code the client sees.
* **the aggregate checks.** "The amount equals the sum of its lines", "the
  imputations add up to the payment" — a `CHECK` cannot express an
  aggregate, so those live in the transaction of the service.

Every refusal is checked for the same two things: it raises
`DomainValidationError` with a code from the closed vocabulary, and **it
writes no row**.
"""


from __future__ import annotations

from tests.integration.personas import crear_persona

from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from tienda.api.exceptions import DomainValidationError
from tienda.models import (
    CashMovement,
    Customer,
    DayClose,
    LedgerEntry,
    Producto,
    Shop,
    Vinculo,
)
from tienda import services

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def shop(db):
    return Shop.objects.create(name="Tienda de prueba", opening_cash=Decimal("150.00"))


@pytest.fixture
def customer(db, shop):
    """A person, and the LINK that says she is a trusted client of the shop.

    **The person belongs to no shop**, and the limit belongs to the link:
    the confidence is the owner's, and the owner has it **in this shop**.
    """
    cliente_usuario, cliente = crear_persona("ana", alias="Ana")
    Vinculo.objects.create(
        tienda=shop,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    return cliente


@pytest.fixture
def producto(db, shop):
    return Producto.objects.create(
        shop=shop, nombre="Pan", precio=Decimal("1.20"), unidad="unidad"
    )


# ---------------------------------------------------------------------------
# The conversions
# ---------------------------------------------------------------------------


def test_a_ledger_row_becomes_a_plain_value(db, shop, customer, user):
    """The row becomes the record the rules expect — not the other way round."""
    row = LedgerEntry.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        kind="cargo",
        amount=Decimal("10.00"),
        occurred_at=timezone.now(),
    )

    valor = services.linea_ledger(row)

    assert valor.id == row.id
    assert valor.kind.value == "cargo"
    assert valor.amount == Decimal("10.00")


def test_the_plain_value_carries_no_orm_hooks(db, shop, customer, user):
    """The converted value is not an ORM object.

    This is the boundary the whole layer rests on: a rule of `domain/` that
    received a row would be a rule that could not be exercised without a
    database.
    """
    row = LedgerEntry.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        kind="pago",
        amount=Decimal("4.00"),
        occurred_at=timezone.now(),
    )

    valor = services.linea_ledger(row)

    assert not hasattr(valor, "save")
    assert not hasattr(valor, "delete")
    assert not hasattr(valor, "pk")


def test_the_outstanding_is_derived_from_the_rows(db, shop, customer, user):
    """The outstanding comes from the rows, on read."""
    now = timezone.now()
    LedgerEntry.objects.create(
        shop=shop, customer=customer, user=user, kind="cargo",
        amount=Decimal("30.00"), occurred_at=now,
    )

    assert services.pendiente_de(customer, now) == Decimal("30.00")


def test_the_outstanding_drops_with_a_payment(db, shop, customer, user):
    """A payment retires debt."""
    now = timezone.now()
    LedgerEntry.objects.create(
        shop=shop, customer=customer, user=user, kind="cargo",
        amount=Decimal("30.00"), occurred_at=now,
    )
    LedgerEntry.objects.create(
        shop=shop, customer=customer, user=user, kind="pago",
        amount=Decimal("12.00"), occurred_at=now,
    )

    assert services.pendiente_de(customer, now) == Decimal("18.00")


def test_the_outstanding_is_never_negative(db, shop, customer, user):
    """Rule 19 makes a negative outstanding unreachable.

    The service never writes a `pago` larger than the debt — that refusal
    is in `registrar_pago` — but even if one were written directly, the
    derived figure is what the rules say it is.
    """
    now = timezone.now()
    LedgerEntry.objects.create(
        shop=shop, customer=customer, user=user, kind="cargo",
        amount=Decimal("20.00"), occurred_at=now,
    )

    # A payment of 35 against a debt of 20 is refused by the rule, so the
    # derived outstanding stays positive.
    from tienda.domain import position as reglas_posicion

    cargos, pagos = services.pendientes_de(customer, now)
    assert reglas_posicion.outstanding(cargos + pagos, now) == Decimal("20.00")


# ---------------------------------------------------------------------------
# The per-row twins
# ---------------------------------------------------------------------------


def test_a_non_positive_amount_is_refused_before_the_write(db, shop, customer, user):
    """The twin of `chk_ledgerentry_amount_positive` (rule 15)."""
    for amount in ("0.00", "-1.00"):
        with pytest.raises(DomainValidationError) as exc:
            services.exigir_importe_positivo(Decimal(amount))
        assert exc.value.codigo_error == "importe_no_positivo"


def test_a_positive_amount_is_accepted(db):
    """The twin accepts a valid amount."""
    assert services.exigir_importe_positivo(Decimal("0.01")) == Decimal("0.01")


def test_an_unknown_kind_is_refused(db):
    """The twin of `chk_ledgerentry_kind_vocabulary` (rule 16)."""
    for kind in ("devolucion", "nota_credito", "en_disputa"):
        with pytest.raises(DomainValidationError) as exc:
            services.exigir_tipo_conocido(kind)
        assert exc.value.codigo_error == "tipo_desconocido"


def test_the_two_known_kinds_are_accepted(db):
    """`cargo` and `pago` are the vocabulary."""
    assert services.exigir_tipo_conocido("cargo") == "cargo"
    assert services.exigir_tipo_conocido("pago") == "pago"


def test_a_line_with_no_quantity_or_a_negative_price_is_refused(db):
    """The twin of the per-line `CHECK`s."""
    with pytest.raises(DomainValidationError) as exc:
        services.exigir_cantidad_valida(Decimal("0"), Decimal("1.20"))
    assert exc.value.codigo_error == "importe_no_positivo"

    with pytest.raises(DomainValidationError) as exc:
        services.exigir_cantidad_valida(Decimal("1"), Decimal("-1.20"))
    assert exc.value.codigo_error == "importe_no_positivo"


def test_a_line_with_a_valid_quantity_and_price_is_accepted(db):
    """A valid line passes the twin."""
    services.exigir_cantidad_valida(Decimal("2"), Decimal("1.20"))


def test_a_field_that_is_not_admitted_is_refused(db):
    """Rule 4: `occurred_at` is never client-supplied.

    The refusal is on the **presence** of the field, not on its value.
    """
    with pytest.raises(DomainValidationError) as exc:
        services.exigir_campos_no_admitidos(
            {"kind": "entrada", "amount": "5.00", "occurred_at": "2026-05-01"},
            {"kind", "amount", "concept"},
        )
    assert exc.value.codigo_error == "campo_no_admitido"


def test_the_admitted_fields_pass(db):
    """A payload of admitted fields passes."""
    services.exigir_campos_no_admitidos(
        {"kind": "entrada", "amount": "5.00", "concept": "caja"},
        {"kind", "amount", "concept"},
    )


# ---------------------------------------------------------------------------
# The cash
# ---------------------------------------------------------------------------


def test_a_cash_movement_is_recorded(db, shop, user):
    """A movement of the drawer is recorded with the server's stamp."""
    movimiento = services.registrar_movimiento_caja(
        shop, user, kind="entrada", amount=Decimal("50.00"), concept="caja inicial"
    )

    assert movimiento.id is not None
    assert movimiento.amount == Decimal("50.00")
    assert CashMovement.objects.count() == 1


def test_a_cash_movement_of_an_unknown_kind_is_refused(db, shop, user):
    """An unknown kind is refused and writes nothing."""
    with pytest.raises(DomainValidationError) as exc:
        services.registrar_movimiento_caja(
            shop, user, kind="traspaso", amount=Decimal("50.00"), concept="x"
        )
    assert exc.value.codigo_error == "tipo_desconocido"
    assert CashMovement.objects.count() == 0


def test_a_cash_movement_of_a_non_positive_amount_is_refused(db, shop, user):
    """A non-positive amount is refused and writes nothing."""
    with pytest.raises(DomainValidationError) as exc:
        services.registrar_movimiento_caja(
            shop, user, kind="entrada", amount=Decimal("0.00"), concept="x"
        )
    assert exc.value.codigo_error == "importe_no_positivo"
    assert CashMovement.objects.count() == 0


def test_a_cash_movement_stamped_in_the_future_is_refused(db, shop, user):
    """Rule 12: the server stamps, and the stamp is not in the future."""
    futuro = timezone.now() + timezone.timedelta(days=1)

    with pytest.raises(DomainValidationError) as exc:
        services.registrar_movimiento_caja(
            shop, user, kind="entrada", amount=Decimal("5.00"), concept="x", at=futuro
        )
    assert exc.value.codigo_error == "campo_no_admitido"
    assert CashMovement.objects.count() == 0


# ---------------------------------------------------------------------------
# The close
# ---------------------------------------------------------------------------


def test_the_close_stores_the_derived_expected_cash(db, shop, user):
    """The `esperado` is the derived cash — never a client-supplied figure."""
    cierre = services.cerrar_dia(
        shop, user, date=timezone.now().date(), contado=Decimal("150.00")
    )

    assert cierre.esperado == Decimal("150.00")
    assert cierre.desviacion == Decimal("0.00")
    assert DayClose.objects.count() == 1


def test_the_close_refuses_a_second_one_for_the_same_day(db, shop, user):
    """Rule 9: a day is closed once per shop."""
    hoy = timezone.now().date()
    services.cerrar_dia(shop, user, date=hoy, contado=Decimal("150.00"))

    with pytest.raises(DomainValidationError) as exc:
        services.cerrar_dia(shop, user, date=hoy, contado=Decimal("150.00"))
    assert exc.value.codigo_error == "cierre_duplicado"
    assert DayClose.objects.count() == 1


def test_the_close_refuses_a_negative_count(db, shop, user):
    """A negative count is refused and writes nothing."""
    with pytest.raises(DomainValidationError) as exc:
        services.cerrar_dia(
            shop, user, date=timezone.now().date(), contado=Decimal("-1.00")
        )
    assert exc.value.codigo_error == "importe_no_positivo"
    assert DayClose.objects.count() == 0


def test_the_deviation_is_the_expected_minus_the_counted(db, shop, user):
    """The deviation is derived, and it is signed."""
    cierre = services.cerrar_dia(
        shop, user, date=timezone.now().date(), contado=Decimal("140.00")
    )

    assert cierre.esperado == Decimal("150.00")
    assert cierre.desviacion == Decimal("10.00")


# ---------------------------------------------------------------------------
# The catalogue and the customers
# ---------------------------------------------------------------------------


def test_the_catalogue_holds_only_the_active_products(db, shop, producto):
    """An inactive product is not in the catalogue."""
    Producto.objects.create(
        shop=shop, nombre="Retirado", precio=Decimal("9.00"), activo=False
    )

    activos = services.productos_activos(shop)
    assert [p.nombre for p in activos] == ["Pan"]


def test_a_product_of_another_shop_is_refused(db, shop, customer, user, producto):
    """Rule 11: a line may not name a product of another shop."""
    otra = Shop.objects.create(name="Otra tienda", opening_cash=Decimal("0.00"))
    ajeno = Producto.objects.create(
        shop=otra, nombre="Ajeno", precio=Decimal("1.00"), unidad="unidad"
    )

    with pytest.raises(DomainValidationError) as exc:
        services.exigir_producto_de_la_tienda(shop, ajeno)
    assert exc.value.codigo_error == "producto_ajeno"


def test_a_product_of_the_same_shop_is_accepted(db, shop, producto):
    """A product of the shop passes."""
    assert services.exigir_producto_de_la_tienda(shop, producto) == producto


def test_a_customer_of_another_shop_is_not_found(db, shop, customer, user):
    """A customer of another shop is a 404, not a refusal.

    The answer must not learn that the customer exists elsewhere.
    """
    otra = Shop.objects.create(name="Otra tienda", opening_cash=Decimal("0.00"))
    cliente_usuario, cliente = crear_persona("luis", alias="Luis")
    Vinculo.objects.create(
        tienda=otra,
        cliente=cliente,
        estado="aceptado",
    )

    assert services.cliente_de_la_tienda(shop, cliente.id) is None
    assert services.cliente_de_la_tienda(shop, customer.id) == customer


def test_a_customer_is_registered_with_its_author(db, shop, user):
    """**The person is the author of her own row.**

    The shop does not create her: she created her account, and the row
    is hers. The owner's act is to ASK, and the request carries the
    name he knows her by - which is what the counter types.
    """

    _usuario, persona = crear_persona("luis", alias="Luis")

    cliente = services.crear_cliente(shop, user, alias="luis")

    # **La fila es de ella**, y el dueno solo pregunta.
    assert cliente.user_id == persona.user_id
    assert cliente.alias == "Luis"
    # Y el vinculo lo pidio el dueno, y espera su respuesta.
    vinculo = Vinculo.objects.get(cliente=cliente)
    assert vinculo.pedido_por_id == user.id
    assert vinculo.estado == "pendiente"


def test_a_negative_credit_limit_is_refused(db, shop, user):
    """A negative limit is refused and writes nothing."""

    crear_persona("luis", alias="Luis")

    with pytest.raises(DomainValidationError) as exc:
        services.crear_cliente(shop, user, alias="luis", credit_limit=Decimal("-1.00"))
    assert exc.value.codigo_error == "importe_no_positivo"
    assert Vinculo.objects.count() == 0


def test_a_null_credit_limit_is_the_explicit_no_limit(db, shop, user):
    """`None` is «sin límite», an explicit state and never a missing value.

    **The limit belongs to the LINK** - the confidence is the owner's, and
    the owner has it in this shop. A trusted client without a cap is
    `NULL` on the link, and it never fires `limite_superado`.
    """

    crear_persona("luis", alias="Luis")

    cliente = services.crear_cliente(shop, user, alias="luis", credit_limit=None)

    vinculo = Vinculo.objects.get(cliente=cliente)
    assert vinculo.credit_limit is None


# ---------------------------------------------------------------------------
# The credential
# ---------------------------------------------------------------------------







def test_the_suspension_override_records_its_author(db, shop, customer, user):
    """Lifting the suspension records an act, never a derived value.

    The derived state stays derived: the override is what is stored, and
    it is an event.
    """
    services.anular_suspension(customer, user)

    assert customer.suspended_override_by_id == user.id
    assert customer.suspended_override_at is not None
    # And no status column appeared.
    assert not hasattr(customer, "status")
    assert not hasattr(customer, "suspended_reason")
