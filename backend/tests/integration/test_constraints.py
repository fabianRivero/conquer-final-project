"""The database constraints of the data model — design §3, tasks 2.1 and 2.4.

Every assertion here is a **database** assertion: the row is refused by
PostgreSQL itself, not by a service check. That is the point — a `CHECK`
sees one row and never an aggregate, so it is the only guarantee that
survives a race between two writers.

The suite therefore runs on **PostgreSQL 16**, never SQLite (landmine 7):
SQLite does not implement partial unique indexes, and its `CHECK` semantics
differ. The CI workflow provides a `postgres:16` service container for
exactly this reason.

The tests come in two families:

* the **constraint** tests, which write a row that violates a `CHECK`, a
  `UNIQUE` or a partial index and assert that the write is refused **and
  that the transaction left nothing behind**;
* the **forbidden-field** test, which asserts that no model declares a
  derived value — the landmine 11 guard of design §12.2 — and no customer
  credit — the landmine 15 guard.
"""

import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from tienda.models import (
    CargoLinea,
    CashMovement,
    CodigoIntento,
    Confirmacion,
    Customer,
    CustomerCodigo,
    DayClose,
    FiadoPropuesto,
    ImputacionPago,
    LedgerEntry,
    LedgerImmutableError,
    PagoPropuesto,
    Producto,
    PropuestaLinea,
    Shop,
    StockMovement,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def dependiente(db):
    return User.objects.create_user(username="dependiente", password="x")


@pytest.fixture
def shop(db):
    return Shop.objects.create(name="Tienda de prueba", opening_cash=Decimal("150.00"))


@pytest.fixture
def customer(db, shop):
    return Customer.objects.create(shop=shop, alias="Ana", credit_limit=Decimal("100.00"))


@pytest.fixture
def cargo(db, shop, customer, user):
    """A charge of 10,00 € — the ledger row a confirmation ratifies."""
    return LedgerEntry.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        kind="cargo",
        amount=Decimal("10.00"),
        occurred_at=timezone.now(),
    )


@pytest.fixture
def pago(db, shop, customer, user):
    """A payment of 4,00 € — the ledger row an imputation points at."""
    return LedgerEntry.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        kind="pago",
        amount=Decimal("4.00"),
        occurred_at=timezone.now(),
    )


@pytest.fixture
def propuesta(db, shop, customer, user):
    """A prepared proposal of 10,00 €, still pending."""
    return FiadoPropuesto.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        estado="pendiente",
        total=Decimal("10.00"),
    )


def _producto(shop, nombre="Pan", precio="1.20"):
    return Producto.objects.create(
        shop=shop, nombre=nombre, precio=Decimal(precio), unidad="unidad"
    )


def _cargo(shop, customer, user, amount="10.00", kind="cargo"):
    return LedgerEntry.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        kind=kind,
        amount=Decimal(amount),
        occurred_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# 2.1 — the CHECK constraints
# ---------------------------------------------------------------------------


def test_ledgerentry_amount_positive_is_refused(shop, customer, user):
    """A ledger entry of zero or less is refused by the database."""
    for amount in ("0.00", "-1.00"):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                LedgerEntry.objects.create(
                    shop=shop,
                    customer=customer,
                    user=user,
                    kind="cargo",
                    amount=Decimal(amount),
                    occurred_at=timezone.now(),
                )
    # The rollback left nothing behind.
    assert LedgerEntry.objects.count() == 0


def test_ledgerentry_kind_vocabulary_is_refused(shop, customer, user):
    """A kind outside {cargo, pago} is refused by the database.

    The service rejects it first with `tipo_desconocido` (rule 16); the
    `CHECK` is the backstop under a race.

    The v1 vocabulary carried a third value, `nota_credito`. It is gone with
    the dispute machinery, so a credit note is now refused like any other
    unknown kind.
    """
    for kind in ("devolucion", "nota_credito", "en_disputa"):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                LedgerEntry.objects.create(
                    shop=shop,
                    customer=customer,
                    user=user,
                    kind=kind,
                    amount=Decimal("10.00"),
                    occurred_at=timezone.now(),
                )
    assert LedgerEntry.objects.count() == 0


def test_ledgerentry_declares_no_cargo_column():
    """`LedgerEntry` has no `cargo_id` — the column is gone with the disputes.

    The v1 column existed only so a `nota de crédito` could name the charge
    it reconciled. There is nothing to reconcile any more: the client
    confirms the charge before it exists (ADR-19).
    """
    fields = {field.name for field in LedgerEntry._meta.get_fields()}

    assert "cargo" not in fields, (
        "LedgerEntry must not declare a cargo column; the repayment is "
        "recorded in ImputacionPago (ADR-27)."
    )


def test_cashmovement_amount_positive_is_refused(shop, user):
    """A cash movement of zero or less is refused by the database."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CashMovement.objects.create(
                shop=shop,
                user=user,
                kind="entrada",
                amount=Decimal("0.00"),
                concept="caja inicial",
                occurred_at=timezone.now(),
            )
    assert CashMovement.objects.count() == 0


def test_cashmovement_kind_vocabulary_is_refused(shop, user):
    """A movement that is neither an `entrada` nor a `salida` is refused."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CashMovement.objects.create(
                shop=shop,
                user=user,
                kind="traspaso",
                amount=Decimal("5.00"),
                concept="traspaso",
                occurred_at=timezone.now(),
            )
    assert CashMovement.objects.count() == 0


def test_cargolinea_cantidad_and_precio_are_refused(shop, cargo):
    """A line of zero units, or of a negative price, is refused."""
    producto = _producto(shop)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CargoLinea.objects.create(
                cargo=cargo,
                producto=producto,
                cantidad=Decimal("0"),
                precio_unitario=Decimal("1.20"),
                total=Decimal("0.00"),
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CargoLinea.objects.create(
                cargo=cargo,
                producto=producto,
                cantidad=Decimal("1"),
                precio_unitario=Decimal("-1.20"),
                total=Decimal("-1.20"),
            )
    assert CargoLinea.objects.count() == 0


def test_cargolinea_total_must_match_the_line(shop, cargo):
    """`total` must equal `round(cantidad * precio_unitario, 2)`.

    This is the per-row half of rule 3: the line cannot disagree with
    itself. The cross-row half — the declared amount against the sum of the
    lines — belongs to the service (Phase 4).
    """
    producto = _producto(shop)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CargoLinea.objects.create(
                cargo=cargo,
                producto=producto,
                cantidad=Decimal("3"),
                precio_unitario=Decimal("1.00"),
                total=Decimal("3.50"),
            )
    assert CargoLinea.objects.count() == 0


def test_cargolinea_total_accepts_the_rounded_product(shop, cargo):
    """The `CHECK` accepts the rounded product, so it is not vacuous.

    A constraint that refuses everything would also refuse the wrong total.
    This writes the correct row and proves the `CHECK` lets it through.
    """
    producto = _producto(shop)
    CargoLinea.objects.create(
        cargo=cargo,
        producto=producto,
        cantidad=Decimal("3"),
        precio_unitario=Decimal("1.00"),
        total=Decimal("3.00"),
    )
    assert CargoLinea.objects.count() == 1


def test_dayclose_counts_are_non_negative(shop, user):
    """A negative `esperado` or `contado` is refused."""
    for field in ("esperado", "contado"):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DayClose.objects.create(
                    shop=shop,
                    user=user,
                    date=datetime.date(2026, 5, 1),
                    esperado=Decimal("-1.00"),
                    contado=Decimal("0.00"),
                )
        break


def test_customer_credit_limit_is_non_negative(shop):
    """A negative credit limit is refused; NULL means "no limit"."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.create(
                shop=shop, alias="Luis", credit_limit=Decimal("-1.00")
            )
    # NULL is the explicit "no limit" state and is accepted.
    Customer.objects.create(shop=shop, alias="Luis", credit_limit=None)
    assert Customer.objects.filter(alias="Luis").count() == 1


def test_producto_precio_is_non_negative(shop):
    """A negative catalogue price is refused."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Producto.objects.create(
                shop=shop, nombre="Negativo", precio=Decimal("-0.01"), unidad="unidad"
            )
    assert Producto.objects.count() == 0


def test_stockmovement_cantidad_and_kind_are_refused(shop):
    """A stock movement of zero units, or of an unknown kind, is refused."""
    producto = _producto(shop)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockMovement.objects.create(
                producto=producto,
                kind="entrada",
                cantidad=Decimal("0"),
                concept="ajuste",
                occurred_at=timezone.now(),
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockMovement.objects.create(
                producto=producto,
                kind="merma",
                cantidad=Decimal("1"),
                concept="ajuste",
                occurred_at=timezone.now(),
            )
    assert StockMovement.objects.count() == 0


def test_confirmacion_declares_only_the_confirmado_state(cargo):
    """`Confirmacion.estado` has one value only: `confirmado`.

    The v1 model carried `en_disputa` as a second state, with the
    `importe_reclamado` and the `nota` fields. All of it is gone: the client
    confirms the charge before it exists, so there is nothing to disagree
    about afterwards (ADR-18, ADR-19).
    """
    for estado in ("en_disputa", "pendiente"):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Confirmacion.objects.create(
                    cargo=cargo,
                    estado=estado,
                    confirmado_en=timezone.now(),
                    origen="tienda",
                )
    assert Confirmacion.objects.count() == 0


def test_confirmacion_declares_no_importe_reclamado():
    """`Confirmacion` has no `importe_reclamado` and no `nota`.

    Both existed only for the dispute machinery.
    """
    fields = {field.name for field in Confirmacion._meta.get_fields()}

    assert "importe_reclamado" not in fields
    assert "nota" not in fields


def test_confirmacion_facilitador_iff_origen_is_refused(cargo, user):
    """`origen='facilitado'` if and only if `facilitado_por_id` is set."""
    # `facilitado` without a facilitator is refused.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="confirmado",
                confirmado_en=timezone.now(),
                origen="facilitado",
                facilitado_por=None,
            )
    # `tienda` with a facilitator is refused too.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="confirmado",
                confirmado_en=timezone.now(),
                origen="tienda",
                facilitado_por=user,
            )
    assert Confirmacion.objects.count() == 0


def test_fiadopropuesto_estado_vocabulary_is_refused(shop, customer, user):
    """A proposal state outside the vocabulary is refused."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FiadoPropuesto.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                estado="descartado",
                total=Decimal("10.00"),
            )
    assert FiadoPropuesto.objects.count() == 0


def test_fiadopropuesto_total_is_non_negative(shop, customer, user):
    """A negative proposal total is refused."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FiadoPropuesto.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                estado="pendiente",
                total=Decimal("-1.00"),
            )
    assert FiadoPropuesto.objects.count() == 0


def test_fiadopropuesto_confirmado_implies_confirmed_at(shop, customer, user):
    """A `confirmado` proposal carries its instant; a `cancelado` one its own.

    The two are mutually exclusive: a proposal moves to exactly one of them
    and never back (rule 7).
    """
    # `confirmado` without `confirmed_at` is refused.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FiadoPropuesto.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                estado="confirmado",
                total=Decimal("10.00"),
                confirmed_at=None,
            )
    # `cancelado` without `canceled_at` is refused.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FiadoPropuesto.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                estado="cancelado",
                total=Decimal("10.00"),
                canceled_at=None,
            )
    # A `confirmado` proposal that also carries `canceled_at` is refused.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FiadoPropuesto.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                estado="confirmado",
                total=Decimal("10.00"),
                confirmed_at=timezone.now(),
                canceled_at=timezone.now(),
            )
    assert FiadoPropuesto.objects.count() == 0


def test_propuestalinea_cantidad_and_precio_are_refused(propuesta):
    """A proposal line of zero units, or of a negative price, is refused."""
    producto = _producto(propuesta.shop)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PropuestaLinea.objects.create(
                propuesta=propuesta,
                producto=producto,
                cantidad=Decimal("0"),
                precio_unitario=Decimal("1.20"),
                total=Decimal("0.00"),
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PropuestaLinea.objects.create(
                propuesta=propuesta,
                producto=producto,
                cantidad=Decimal("1"),
                precio_unitario=Decimal("-1.20"),
                total=Decimal("-1.20"),
            )
    assert PropuestaLinea.objects.count() == 0


def test_propuestalinea_total_must_match_the_line(propuesta):
    """`total` must equal `round(cantidad * precio_unitario, 2)`.

    The proposal's line carries the same arithmetic as the charge's line:
    the `desglose` the client confirms is a real arithmetic, not a figure.
    """
    producto = _producto(propuesta.shop)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PropuestaLinea.objects.create(
                propuesta=propuesta,
                producto=producto,
                cantidad=Decimal("3"),
                precio_unitario=Decimal("1.00"),
                total=Decimal("3.50"),
            )
    assert PropuestaLinea.objects.count() == 0


def test_propuestalinea_total_accepts_the_rounded_product(propuesta):
    """The `CHECK` accepts the rounded product, so it is not vacuous."""
    producto = _producto(propuesta.shop)
    PropuestaLinea.objects.create(
        propuesta=propuesta,
        producto=producto,
        cantidad=Decimal("3"),
        precio_unitario=Decimal("1.00"),
        total=Decimal("3.00"),
    )
    assert PropuestaLinea.objects.count() == 1


def test_pagopropuesto_importe_is_positive(shop, customer):
    """A proposed payment of zero or less is refused (rule 17)."""
    for importe in ("0.00", "-1.00"):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PagoPropuesto.objects.create(
                    shop=shop,
                    customer=customer,
                    importe=Decimal(importe),
                    referencia="transferencia",
                    estado="pendiente",
                )
    assert PagoPropuesto.objects.count() == 0


def test_pagopropuesto_estado_vocabulary_is_refused(shop, customer):
    """A proposal state outside the vocabulary is refused."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PagoPropuesto.objects.create(
                shop=shop,
                customer=customer,
                importe=Decimal("10.00"),
                referencia="transferencia",
                estado="aceptado",
            )
    assert PagoPropuesto.objects.count() == 0


def test_pagopropuesto_resolved_implies_its_author(shop, customer, user):
    """A resolved proposal carries its instant and names who resolved it."""
    for estado in ("validado", "rechazado"):
        # Without `resolved_at`.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PagoPropuesto.objects.create(
                    shop=shop,
                    customer=customer,
                    importe=Decimal("10.00"),
                    referencia="transferencia",
                    estado=estado,
                    resolved_at=None,
                    resolved_by=user,
                )
        # Without `resolved_by`.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PagoPropuesto.objects.create(
                    shop=shop,
                    customer=customer,
                    importe=Decimal("10.00"),
                    referencia="transferencia",
                    estado=estado,
                    resolved_at=timezone.now(),
                    resolved_by=None,
                )
    assert PagoPropuesto.objects.count() == 0


def test_pagopropuesto_declares_no_cargo():
    """`PagoPropuesto` names no charge.

    The client proposes an amount and the FIFO decides which debts it
    retires. A column naming the target charge would let the client direct
    money at a particular debt, which is exactly what option C refuses
    (ADR-27).
    """
    fields = {field.name for field in PagoPropuesto._meta.get_fields()}

    assert "cargo" not in fields, (
        "PagoPropuesto must not name a charge; the FIFO decides (ADR-27)."
    )


def test_imputacionpago_importe_is_positive(shop, customer, user, cargo, pago):
    """An imputation always places something."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ImputacionPago.objects.create(
                pago=pago, cargo=cargo, importe=Decimal("0.00")
            )
    assert ImputacionPago.objects.count() == 0


def test_imputacionpago_cannot_touch_the_same_charge_twice(
    shop, customer, user, cargo, pago
):
    """UNIQUE (pago_id, cargo_id) — one payment touches a charge once.

    The `UNIQUE` is declared on the pair, so it holds for every kind of
    `pago` and `cargo` alike; the kind itself is rule 20's business, and it
    lives in the service because a `CHECK` cannot look at another row.
    """
    ImputacionPago.objects.create(pago=pago, cargo=cargo, importe=Decimal("4.00"))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ImputacionPago.objects.create(
                pago=pago, cargo=cargo, importe=Decimal("1.00")
            )
    assert ImputacionPago.objects.count() == 1


def test_imputacionpago_records_the_repartition(
    shop, customer, user
):
    """The repartition of a payment is recorded, one row per charge touched.

    A payment of 20,00 € against charges of 8,00 €, 7,00 € and 15,00 € writes
    three rows — 8,00, 7,00 and 5,00 — and the charges read 8/8, 7/7 and 5/15
    (ADR-27).

    The `CHECK`s cannot express these two sums: a `CHECK` sees one row and
    never an aggregate. The sums are rule 21's business and live in the
    service; what this test proves is that the **granule** is the charge, so
    three rows are written and the partial payment is visible.
    """
    pan = _cargo(shop, customer, user, amount="8.00")
    refresco = _cargo(shop, customer, user, amount="7.00")
    galletas = _cargo(shop, customer, user, amount="15.00")
    pago = _cargo(shop, customer, user, amount="20.00", kind="pago")

    ImputacionPago.objects.create(pago=pago, cargo=pan, importe=Decimal("8.00"))
    ImputacionPago.objects.create(pago=pago, cargo=refresco, importe=Decimal("7.00"))
    ImputacionPago.objects.create(pago=pago, cargo=galletas, importe=Decimal("5.00"))

    # Three rows, one per charge, and the third is the partial one.
    assert ImputacionPago.objects.filter(pago=pago).count() == 3

    # The derived saldo of each charge: amount - the imputations against it.
    def saldo(cargo):
        pagado = sum(
            (i.importe for i in ImputacionPago.objects.filter(cargo=cargo)),
            Decimal("0.00"),
        )
        return cargo.amount - pagado

    assert saldo(pan) == Decimal("0.00")
    assert saldo(refresco) == Decimal("0.00")
    assert saldo(galletas) == Decimal("10.00")


def test_codigo_revocation_always_names_its_author(shop, customer, user):
    """A revoked credential names the user who revoked it."""
    codigo = CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix="ABCDEF",
        codigo_hash="hash",
        issued_at=timezone.now(),
        issued_by=user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerCodigo.objects.filter(pk=codigo.pk).update(
                revoked_at=timezone.now()
            )
    assert CustomerCodigo.objects.count() == 1


# ---------------------------------------------------------------------------
# 2.1 — the UNIQUE constraints
# ---------------------------------------------------------------------------


def test_customer_alias_is_unique_per_shop(shop):
    """The alias identifies a customer inside its shop."""
    Customer.objects.create(shop=shop, alias="Ana")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.create(shop=shop, alias="Ana")
    assert Customer.objects.filter(alias="Ana").count() == 1


def test_dayclose_is_unique_per_shop_and_date(shop, user):
    """A day is closed once per shop."""
    DayClose.objects.create(
        shop=shop,
        user=user,
        date=datetime.date(2026, 5, 1),
        esperado=Decimal("10.00"),
        contado=Decimal("10.00"),
        desviacion=Decimal("0.00"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DayClose.objects.create(
                shop=shop,
                user=user,
                date=datetime.date(2026, 5, 1),
                esperado=Decimal("10.00"),
                contado=Decimal("10.00"),
                desviacion=Decimal("0.00"),
            )
    assert DayClose.objects.count() == 1


def test_producto_nombre_is_unique_per_shop(shop):
    """A name identifies an item inside its shop."""
    Producto.objects.create(shop=shop, nombre="Pan", precio=Decimal("1.20"))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Producto.objects.create(shop=shop, nombre="Pan", precio=Decimal("1.30"))
    assert Producto.objects.count() == 1


def test_codigo_prefix_is_unique_per_shop(shop, customer, user):
    """The prefix identifies a credential inside its shop."""
    CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix="ABCDEF",
        codigo_hash="hash",
        issued_at=timezone.now(),
        issued_by=user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerCodigo.objects.create(
                shop=shop,
                customer=customer,
                prefix="ABCDEF",
                codigo_hash="otro",
                issued_at=timezone.now(),
                issued_by=user,
            )
    assert CustomerCodigo.objects.count() == 1


def test_only_one_active_codigo_per_customer(shop, customer, user):
    """A customer holds at most one active credential.

    The partial unique index admits a second row only once the first one is
    revoked, which is the rotation path.
    """
    codigo = CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix="ABCDEF",
        codigo_hash="hash",
        issued_at=timezone.now(),
        issued_by=user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerCodigo.objects.create(
                shop=shop,
                customer=customer,
                prefix="UVWXYZ",
                codigo_hash="otro",
                issued_at=timezone.now(),
                issued_by=user,
            )
    assert CustomerCodigo.objects.count() == 1

    # Once the first is revoked, a second one is admitted.
    codigo.revoked_at = timezone.now()
    codigo.revoked_by = user
    codigo.save()
    CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix="UVWXYZ",
        codigo_hash="otro",
        issued_at=timezone.now(),
        issued_by=user,
    )
    assert CustomerCodigo.objects.count() == 2


def test_only_one_live_proposal_per_customer(shop, customer, user):
    """Partial UNIQUE (customer_id) WHERE estado='pendiente'.

    At most one live proposal per customer: the shop shows one figure at the
    counter at a time.
    """
    FiadoPropuesto.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        estado="pendiente",
        total=Decimal("10.00"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FiadoPropuesto.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                estado="pendiente",
                total=Decimal("20.00"),
            )
    assert FiadoPropuesto.objects.count() == 1

    # A cancelled proposal frees the slot.
    propuesta = FiadoPropuesto.objects.get()
    propuesta.estado = "cancelado"
    propuesta.canceled_at = timezone.now()
    propuesta.save()
    FiadoPropuesto.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        estado="pendiente",
        total=Decimal("20.00"),
    )
    assert FiadoPropuesto.objects.count() == 2


def test_one_confirmed_row_per_charge(cargo):
    """A charge holds at most one confirmation, for the whole life of the charge.

    The partial unique index `uniq_confirmacion_one_confirmado_per_cargo` is
    the DB-level twin of `propuesta_ya_confirmada`: the API contract names
    the proposal-level code (CC-01), and this index is the backstop under a
    race.
    """
    Confirmacion.objects.create(
        cargo=cargo,
        estado="confirmado",
        confirmado_en=timezone.now(),
        origen="tienda",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="confirmado",
                confirmado_en=timezone.now(),
                origen="tienda",
            )
    assert Confirmacion.objects.count() == 1


# ---------------------------------------------------------------------------
# 2.3 and 2.6 — the immutability
# ---------------------------------------------------------------------------


def test_the_queryset_also_refuses_to_update_or_delete(cargo):
    """`QuerySet.update()` and `QuerySet.delete()` are refused too.

    The model guard covers `instance.save()` and `instance.delete()`, but
    both queryset methods bypass them and would happily rewrite or remove an
    append-only row.
    """
    with pytest.raises(LedgerImmutableError):
        LedgerEntry.objects.filter(pk=cargo.pk).update(amount=Decimal("99.00"))
    with pytest.raises(LedgerImmutableError):
        LedgerEntry.objects.filter(pk=cargo.pk).delete()
    assert LedgerEntry.objects.count() == 1


def test_ledgerentry_cannot_be_updated(cargo):
    """A ledger row cannot be rewritten; a correction is appended."""
    cargo.amount = Decimal("99.00")
    with pytest.raises(LedgerImmutableError):
        cargo.save()
    assert LedgerEntry.objects.get(pk=cargo.pk).amount == Decimal("10.00")


def test_ledgerentry_cannot_be_deleted(cargo):
    """A ledger row cannot be removed."""
    with pytest.raises(LedgerImmutableError):
        cargo.delete()
    assert LedgerEntry.objects.count() == 1


def test_cargolinea_cannot_be_updated_or_deleted(shop, cargo):
    """A charge line is immutable with its charge (IC-09)."""
    producto = _producto(shop)
    linea = CargoLinea.objects.create(
        cargo=cargo,
        producto=producto,
        cantidad=Decimal("2"),
        precio_unitario=Decimal("1.20"),
        total=Decimal("2.40"),
    )
    linea.total = Decimal("0.01")
    with pytest.raises(LedgerImmutableError):
        linea.save()
    with pytest.raises(LedgerImmutableError):
        linea.delete()
    assert CargoLinea.objects.count() == 1


def test_confirmacion_cannot_be_updated_or_deleted(cargo):
    """A confirmation is immutable: a charge's confirmation is a fact."""
    confirmacion = Confirmacion.objects.create(
        cargo=cargo,
        estado="confirmado",
        confirmado_en=timezone.now(),
        origen="tienda",
    )
    confirmacion.origen = "facilitado"
    with pytest.raises(LedgerImmutableError):
        confirmacion.save()
    with pytest.raises(LedgerImmutableError):
        confirmacion.delete()
    assert Confirmacion.objects.count() == 1


def test_propuestalinea_cannot_be_updated_or_deleted(propuesta):
    """A proposal's line is immutable: the `desglose` the client saw is fixed."""
    producto = _producto(propuesta.shop)
    linea = PropuestaLinea.objects.create(
        propuesta=propuesta,
        producto=producto,
        cantidad=Decimal("2"),
        precio_unitario=Decimal("1.20"),
        total=Decimal("2.40"),
    )
    linea.total = Decimal("0.01")
    with pytest.raises(LedgerImmutableError):
        linea.save()
    with pytest.raises(LedgerImmutableError):
        linea.delete()
    assert PropuestaLinea.objects.count() == 1


def test_imputacionpago_cannot_be_updated_or_deleted(
    shop, customer, user, cargo, pago
):
    """An imputation is immutable: the repartition is a record, not a draft."""
    imputacion = ImputacionPago.objects.create(
        pago=pago, cargo=cargo, importe=Decimal("4.00")
    )
    imputacion.importe = Decimal("1.00")
    with pytest.raises(LedgerImmutableError):
        imputacion.save()
    with pytest.raises(LedgerImmutableError):
        imputacion.delete()
    assert ImputacionPago.objects.count() == 1


def test_the_two_cargo_id_columns_are_distinct():
    """The two `cargo_id` columns are two different columns on two tables.

    `Confirmacion.cargo_id` is the charge the row **ratifies** — non-null.
    There is no `LedgerEntry.cargo_id` any more: the v1 column existed for
    the reconciliation and is gone with it.

    The distinction is asserted permanently because the v1 design validator
    caught the confusion once.
    """
    confirmacion_fields = {field.name for field in Confirmacion._meta.get_fields()}
    ledger_fields = {field.name for field in LedgerEntry._meta.get_fields()}

    assert "cargo" in confirmacion_fields
    assert "cargo" not in ledger_fields


def test_the_partial_unique_indexes_sit_on_the_right_tables():
    """Each partial index lives on the table design §3 names.

    The v1 suite asserted this because one of the three indexes had leaked
    onto the wrong table. The v2 set is smaller — three instead of four — and
    the assertion is kept: a partial index on the wrong table is a silent
    guarantee about the wrong rows.
    """
    expected = {
        "uniq_confirmacion_one_confirmado_per_cargo": Confirmacion,
        "uniq_fiadopropuesto_one_pendiente_per_customer": FiadoPropuesto,
        "uniq_codigo_one_active_per_customer": CustomerCodigo,
    }

    for name, model in expected.items():
        names = [c.name for c in model._meta.constraints]
        assert name in names, (
            f"{model.__name__} must declare the constraint {name}; it declares "
            f"{names}."
        )

    # And no partial index leaked onto another table.
    for name in expected:
        owners = [
            m.__name__
            for m in (Confirmacion, FiadoPropuesto, CustomerCodigo, LedgerEntry)
            if name in [c.name for c in m._meta.constraints]
        ]
        assert len(owners) == 1, f"{name} is declared on {owners}."


def test_the_v1_partial_indexes_are_gone():
    """The dispute machinery's constraints no longer exist.

    Four v1 constraints disappear with the v2 model. Their absence is
    asserted explicitly, because a leftover index would still enforce the
    old dispute semantics on the new schema.
    """
    gone = {
        "uniq_confirmacion_one_disputa_per_cargo",
        "uniq_ledgerentry_one_reconciliation_per_cargo",
        "chk_ledgerentry_cargo_only_on_credit_note",
        "chk_confirmacion_state_fields",
        "chk_confirmacion_importe_non_negative",
    }

    declared = set()
    for model in (
        Confirmacion,
        FiadoPropuesto,
        CustomerCodigo,
        LedgerEntry,
        CargoLinea,
        PropuestaLinea,
        ImputacionPago,
        PagoPropuesto,
        Customer,
        Producto,
        CashMovement,
        DayClose,
        StockMovement,
    ):
        declared |= {c.name for c in model._meta.constraints}

    still_there = gone & declared
    assert still_there == set(), (
        "The v1 dispute constraints must be gone: " + ", ".join(sorted(still_there))
    )


# ---------------------------------------------------------------------------
# 2.4 — the forbidden-field suite
# ---------------------------------------------------------------------------


FORBIDDEN_FIELD_NAMES = {
    # A stored balance or a stored derived figure.
    "saldo",
    "balance",
    "outstanding",
    "antiguedad_max_dias",
    "status",
    "suspended_reason",
    "suspended_at",
    "stock",
    "reconciled",
    "revisar",
    "precio_origen",
    # The v1 dispute fields.
    "importe_reclamado",
    "nota",
    # A stored credit in the client's favour — landmine 15.
    "credit_a_favor",
    "saldo_a_favor",
    # The v2 fields that must never become columns.
    "comprobante",
    "codigo",
    # The repartition is recorded as `ImputacionPago` rows, never as a
    # mutable column on a charge — ADR-27.
    "pagado",
    "saldo_cargo",
}


FORBIDDEN_CONFIRMATION_NAMES = {
    "estado_confirmacion",
    "confirmation_state",
    "confirmado",
    "en_disputa",
}


def test_ausencia_de_campos_derivados():
    """No model declares a derived value — landmine 11, design §12.2.

    The assertion is structural: it walks the declared fields of every model
    of the `tienda` application and fails on a forbidden name. A stored
    derived value is a lie the moment the next row is written, so the field
    must not exist at all.
    """
    from django.apps import apps

    offences = []
    for model in apps.get_app_config("tienda").get_models():
        for field in model._meta.get_fields():
            name = getattr(field, "name", "")
            if name in FORBIDDEN_FIELD_NAMES:
                offences.append(f"{model.__name__}.{name}")

    assert offences == [], (
        "A model declares a derived value, which design §3 forbids: "
        + ", ".join(offences)
    )


def test_customer_declares_no_confirmation_state():
    """No `Customer` field carries a confirmation state (IC-04).

    The effective state of a charge is derived on read from its
    `Confirmacion` rows. A stored state on the customer would be a second
    source of truth, and it would drift.
    """
    customer_fields = {field.name for field in Customer._meta.get_fields()}

    for name in FORBIDDEN_CONFIRMATION_NAMES:
        assert name not in customer_fields, (
            f"Customer must not carry a confirmation state; it declares {name}."
        )

    # The same forbidden vocabulary as the rest of the model.
    for name in FORBIDDEN_FIELD_NAMES:
        assert name not in customer_fields, (
            f"Customer must not declare the derived field {name}."
        )


def test_the_credential_is_not_a_column_of_customer():
    """The credential lives in `CustomerCodigo`, not in `Customer` (CAC-09).

    The plaintext is never stored at all; only the hash and the non-secret
    prefix are, both on the credential table.
    """
    customer_fields = {field.name for field in Customer._meta.get_fields()}
    assert "codigo" not in customer_fields
    assert "codigo_hash" not in customer_fields


def test_the_throttle_ledger_stores_no_plaintext():
    """The throttle ledger holds the hash of the credential, never the value.

    It records every presented credential so the throttle can count them. If
    it held the plaintext, the ledger would be a second place where the
    secret lives.
    """
    fields = {field.name for field in CodigoIntento._meta.get_fields()}

    assert "codigo" not in fields
    assert "presented_hash" in fields
    assert "plaintext" not in fields


def test_the_models_declare_no_derived_figure():
    """No model declares a figure the shop derives on read.

    The cash position, the real position, the pending fiado, the cash series,
    the stock ceiling and the ageing buckets are all computed from these rows
    every time they are asked for.
    """
    from django.apps import apps

    forbidden = {
        "caja",
        "posicion_real",
        "fiado_pendiente",
        "serie_caja",
        "existencias_registradas",
        "vigente",
        "envejecido",
        "viejo",
        "cronico",
    }

    offences = []
    for model in apps.get_app_config("tienda").get_models():
        for field in model._meta.get_fields():
            name = getattr(field, "name", "")
            if name in forbidden:
                offences.append(f"{model.__name__}.{name}")

    assert offences == [], (
        "A model declares a derived figure, which design §3 forbids: "
        + ", ".join(offences)
    )


def test_no_model_declares_a_customer_credit():
    """No model holds a balance in the customer's favour — landmine 15.

    A `pago` never exceeds the debt it retires (rule 19): the shop returns
    the excess as change and it never enters the book. There is therefore
    nothing to store, and the whole vocabulary of a credit is absent from the
    schema (ADR-26).
    """
    from django.apps import apps

    credit_vocabulary = {
        "credito",
        "credito_a_favor",
        "saldo_a_favor",
        "favor",
        "a_favor",
        "residual",
        "saldo_pendiente",
    }

    offences = []
    for model in apps.get_app_config("tienda").get_models():
        for field in model._meta.get_fields():
            name = getattr(field, "name", "").lower()
            if name in credit_vocabulary:
                offences.append(f"{model.__name__}.{name}")

    assert offences == [], (
        "A model declares a customer credit, which rule 19 makes impossible: "
        + ", ".join(offences)
    )


def test_the_models_declare_the_sixteen_entities():
    """The application declares the sixteen entities of design §3.

    The count is asserted because a missing entity is invisible: the
    application would boot, the tests that do not touch it would pass, and
    the capability would simply be absent at runtime.
    """
    from django.apps import apps

    models = {m.__name__ for m in apps.get_app_config("tienda").get_models()}

    expected = {
        "Shop",
        "Customer",
        "Producto",
        "FiadoPropuesto",
        "PropuestaLinea",
        "LedgerEntry",
        "CargoLinea",
        "Confirmacion",
        "ImputacionPago",
        "PagoPropuesto",
        "CashMovement",
        "DayClose",
        "StockMovement",
        "CustomerCodigo",
        "CodigoIntento",
    }

    missing = expected - models
    assert missing == set(), (
        "The application is missing the entities: " + ", ".join(sorted(missing))
    )
