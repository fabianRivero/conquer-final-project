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
  derived value — the landmine 11 guard of design §12.2.
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
    LedgerEntry,
    LedgerImmutableError,
    Producto,
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


def _producto(shop, nombre="Pan", precio="1.20"):
    return Producto.objects.create(
        shop=shop, nombre=nombre, precio=Decimal(precio), unidad="unidad"
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
    """A kind outside {cargo, pago, nota_credito} is refused by the database.

    The service rejects it first with `tipo_desconocido` (rule 17); the
    `CHECK` is the backstop under a race.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LedgerEntry.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                kind="devolucion",
                amount=Decimal("10.00"),
                occurred_at=timezone.now(),
            )
    assert LedgerEntry.objects.count() == 0


def test_ledgerentry_cargo_only_on_a_credit_note(shop, customer, user):
    """Only a credit note may name the charge it reconciles."""
    cargo = LedgerEntry.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        kind="cargo",
        amount=Decimal("10.00"),
        occurred_at=timezone.now(),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LedgerEntry.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                kind="pago",
                amount=Decimal("4.00"),
                occurred_at=timezone.now(),
                cargo=cargo,
            )
    assert LedgerEntry.objects.count() == 1


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
    """The matching total is accepted — the constraint is not vacuous."""
    producto = _producto(shop)
    linea = CargoLinea.objects.create(
        cargo=cargo,
        producto=producto,
        cantidad=Decimal("3"),
        precio_unitario=Decimal("1.00"),
        total=Decimal("3.00"),
    )
    assert linea.total == Decimal("3.00")


def test_dayclose_counts_are_non_negative(shop, user):
    """A negative `esperado` or `contado` is refused."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DayClose.objects.create(
                shop=shop,
                user=user,
                date=datetime.date(2026, 1, 31),
                esperado=Decimal("-1.00"),
                contado=Decimal("0.00"),
                desviacion=Decimal("-1.00"),
            )
    assert DayClose.objects.count() == 0


def test_customer_credit_limit_is_non_negative(shop):
    """A negative credit limit is refused; NULL still means "no limit"."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.create(
                shop=shop, alias="Bruno", credit_limit=Decimal("-5.00")
            )
    sin_limite = Customer.objects.create(shop=shop, alias="Carla")
    assert sin_limite.credit_limit is None
    assert Customer.objects.count() == 1


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
                concept="recepcion",
                occurred_at=timezone.now(),
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockMovement.objects.create(
                producto=producto,
                kind="merma",
                cantidad=Decimal("1"),
                concept="rotura",
                occurred_at=timezone.now(),
            )
    assert StockMovement.objects.count() == 0


def test_confirmacion_state_fields_are_refused(cargo):
    """`confirmado` demands the instant and claims no amount.

    `en_disputa` claims an amount and carries no instant. A row that mixes
    the two is refused by the database.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="confirmado",
                confirmado_en=timezone.now(),
                importe_reclamado=Decimal("5.00"),
                origen="cliente",
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="en_disputa",
                importe_reclamado=Decimal("5.00"),
                confirmado_en=timezone.now(),
                origen="cliente",
            )
    assert Confirmacion.objects.count() == 0


def test_confirmacion_facilitador_iff_origen_is_refused(cargo, user):
    """`origen='facilitado'` if and only if a facilitator is named."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="confirmado",
                confirmado_en=timezone.now(),
                origen="facilitado",
            )
    assert Confirmacion.objects.count() == 0


def test_confirmacion_importe_reclamado_is_non_negative(cargo):
    """A dispute claiming a negative amount is refused."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="en_disputa",
                importe_reclamado=Decimal("-1.00"),
                origen="cliente",
            )
    assert Confirmacion.objects.count() == 0


def test_codigo_revocation_always_names_its_author(shop, customer, user):
    """A revocation records an act, so it always names the author."""
    codigo = CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix="AB12CD",
        codigo_hash="hash-1",
        issued_at=timezone.now(),
        issued_by=user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerCodigo.objects.filter(pk=codigo.pk).update(revoked_at=timezone.now())
    assert CustomerCodigo.objects.count() == 1


# ---------------------------------------------------------------------------
# 2.1 — the UNIQUE constraints and the partial unique indexes
# ---------------------------------------------------------------------------


def test_customer_alias_is_unique_per_shop(shop):
    """UNIQUE (shop_id, alias) — the alias identifies a customer in its shop.

    The same alias in another shop is a different customer, so the constraint
    is scoped to the shop.
    """
    Customer.objects.create(shop=shop, alias="Ana")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.create(shop=shop, alias="Ana")
    assert Customer.objects.filter(shop=shop, alias="Ana").count() == 1

    otra = Shop.objects.create(name="Otra tienda", opening_cash=Decimal("0.00"))
    Customer.objects.create(shop=otra, alias="Ana")
    assert Customer.objects.count() == 2


def test_dayclose_is_unique_per_shop_and_date(shop, user):
    """UNIQUE (shop_id, date) — a day is closed once per shop (rule 8)."""
    fecha = datetime.date(2026, 1, 31)
    DayClose.objects.create(
        shop=shop,
        user=user,
        date=fecha,
        esperado=Decimal("150.00"),
        contado=Decimal("150.00"),
        desviacion=Decimal("0.00"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DayClose.objects.create(
                shop=shop,
                user=user,
                date=fecha,
                esperado=Decimal("150.00"),
                contado=Decimal("140.00"),
                desviacion=Decimal("10.00"),
            )
    assert DayClose.objects.count() == 1


def test_producto_nombre_is_unique_per_shop(shop):
    """UNIQUE (shop_id, nombre) — a name identifies an item in its shop."""
    _producto(shop, nombre="Pan")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _producto(shop, nombre="Pan")
    assert Producto.objects.count() == 1


def test_codigo_prefix_is_unique_per_shop(shop, customer, user):
    """UNIQUE (shop_id, prefix) — the prefix identifies a credential."""
    CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix="AB12CD",
        codigo_hash="hash-1",
        issued_at=timezone.now(),
        issued_by=user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerCodigo.objects.create(
                shop=shop,
                customer=customer,
                prefix="AB12CD",
                codigo_hash="hash-2",
                issued_at=timezone.now(),
                issued_by=user,
            )
    assert CustomerCodigo.objects.count() == 1


def test_only_one_active_codigo_per_customer(shop, customer, user):
    """Partial UNIQUE (customer_id) WHERE revoked_at IS NULL.

    A customer holds at most one active credential. A second one is refused
    while the first is unrevoked, and admitted once the first is revoked.
    """
    CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix="AB12CD",
        codigo_hash="hash-1",
        issued_at=timezone.now(),
        issued_by=user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerCodigo.objects.create(
                shop=shop,
                customer=customer,
                prefix="XY78ZW",
                codigo_hash="hash-2",
                issued_at=timezone.now(),
                issued_by=user,
            )
    assert CustomerCodigo.objects.count() == 1

    # The first credential is revoked, so the second one is admitted.
    CustomerCodigo.objects.filter(prefix="AB12CD").update(
        revoked_at=timezone.now(), revoked_by=user
    )
    CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix="XY78ZW",
        codigo_hash="hash-2",
        issued_at=timezone.now(),
        issued_by=user,
    )
    assert CustomerCodigo.objects.count() == 2
    assert (
        CustomerCodigo.objects.filter(customer=customer, revoked_at__isnull=True).count()
        == 1
    )


def test_one_confirmed_row_per_charge(cargo):
    """Partial UNIQUE (cargo_id) WHERE estado='confirmado'.

    At most one confirmation per charge, for the whole life of the charge
    (rule 6).
    """
    Confirmacion.objects.create(
        cargo=cargo,
        estado="confirmado",
        confirmado_en=timezone.now(),
        origen="cliente",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="confirmado",
                confirmado_en=timezone.now(),
                origen="dueno",
            )
    assert Confirmacion.objects.count() == 1


def test_one_dispute_row_per_charge(cargo):
    """Partial UNIQUE (cargo_id) WHERE estado='en_disputa' (rule 7)."""
    Confirmacion.objects.create(
        cargo=cargo,
        estado="en_disputa",
        importe_reclamado=Decimal("8.00"),
        origen="cliente",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Confirmacion.objects.create(
                cargo=cargo,
                estado="en_disputa",
                importe_reclamado=Decimal("7.00"),
                origen="cliente",
            )
    assert Confirmacion.objects.count() == 1


def test_a_charge_accumulates_one_row_per_state(cargo):
    """The two indexes are per state, so `confirmado -> en_disputa` is legal.

    The rows accumulate; only a second row with the *same* state is
    refused. This is what makes the append-only history work.
    """
    Confirmacion.objects.create(
        cargo=cargo,
        estado="confirmado",
        confirmado_en=timezone.now(),
        origen="cliente",
    )
    Confirmacion.objects.create(
        cargo=cargo,
        estado="en_disputa",
        importe_reclamado=Decimal("8.00"),
        origen="cliente",
    )
    assert Confirmacion.objects.count() == 2
    assert Confirmacion.objects.filter(cargo=cargo).count() == 2


def test_the_queryset_also_refuses_to_update_or_delete(cargo):
    """`QuerySet.update()` and `QuerySet.delete()` are refused too.

    The model guard covers `instance.save()` and `instance.delete()`, but
    the queryset methods bypass both of them. Design §3 says these three
    tables are append-only, so the queryset closes the same hole.
    """
    with pytest.raises(LedgerImmutableError):
        LedgerEntry.objects.filter(pk=cargo.pk).update(amount=Decimal("99.00"))
    with pytest.raises(LedgerImmutableError):
        LedgerEntry.objects.filter(pk=cargo.pk).delete()

    cargo.refresh_from_db()
    assert cargo.amount == Decimal("10.00")
    assert LedgerEntry.objects.count() == 1


def test_the_two_cargo_id_columns_are_distinct():
    """`Confirmacion.cargo_id` and `LedgerEntry.cargo_id` are different.

    `Confirmacion.cargo_id` names the charge a confirmation row ratifies.
    `LedgerEntry.cargo_id` names the charge a credit note reconciles. They
    are different columns on different tables, and confusing the two is the
    mistake the design validator caught once — so the distinction is
    asserted here rather than left to a reader.
    """
    confirmacion_cargo = Confirmacion._meta.get_field("cargo")
    ledger_cargo = LedgerEntry._meta.get_field("cargo")

    # Both point at the `LedgerEntry` of a charge...
    assert confirmacion_cargo.related_model is LedgerEntry
    assert ledger_cargo.related_model is LedgerEntry

    # ...but they are different fields, on different tables, with different
    # reverse relations.
    assert confirmacion_cargo is not ledger_cargo
    assert confirmacion_cargo.model is Confirmacion
    assert ledger_cargo.model is LedgerEntry
    assert confirmacion_cargo.remote_field.related_name == "confirmaciones"
    assert ledger_cargo.remote_field.related_name == "reconciliations"

    # The charge a confirmation ratifies is always present.
    assert confirmacion_cargo.null is False


def test_the_three_partial_unique_indexes_sit_on_the_right_tables():
    """Each partial unique index lives on the table design §3 names.

    The design declares three partial unique indexes across two tables, and
    every one of them must exist:

    * `Confirmacion` — partial UNIQUE `(cargo_id)` WHERE `estado='confirmado'`;
    * `Confirmacion` — partial UNIQUE `(cargo_id)` WHERE `estado='en_disputa'`;
    * `LedgerEntry`  — partial UNIQUE `(cargo_id)` WHERE `kind='nota_credito'`.
    """
    ledger_constraints = {c.name: c for c in LedgerEntry._meta.constraints}
    confirmacion_constraints = {c.name: c for c in Confirmacion._meta.constraints}

    assert "uniq_ledgerentry_one_reconciliation_per_cargo" in ledger_constraints
    assert "uniq_confirmacion_one_confirmado_per_cargo" in confirmacion_constraints
    assert "uniq_confirmacion_one_disputa_per_cargo" in confirmacion_constraints

    # The two Confirmacion indexes must not have leaked onto LedgerEntry, and
    # the LedgerEntry index must not have leaked onto Confirmacion.
    assert "uniq_confirmacion_one_confirmado_per_cargo" not in ledger_constraints
    assert "uniq_confirmacion_one_disputa_per_cargo" not in ledger_constraints
    assert "uniq_ledgerentry_one_reconciliation_per_cargo" not in confirmacion_constraints

    # Each one is a partial index, and it is filtered on the right column.
    reconciling = ledger_constraints["uniq_ledgerentry_one_reconciliation_per_cargo"]
    assert reconciling.condition is not None
    assert "nota_credito" in str(reconciling.condition)

    confirmado = confirmacion_constraints["uniq_confirmacion_one_confirmado_per_cargo"]
    disputa = confirmacion_constraints["uniq_confirmacion_one_disputa_per_cargo"]
    assert confirmado.condition is not None
    assert disputa.condition is not None
    assert "confirmado" in str(confirmado.condition)
    assert "en_disputa" in str(disputa.condition)


def test_a_charge_is_reconciled_at_most_once(shop, customer, user, cargo):
    """Partial UNIQUE (cargo_id) WHERE kind='nota_credito' (rule 5).

    The credit note that reconciles a dispute is unique per charge, for the
    whole life of the charge. A plain credit note, which names no charge,
    is unaffected.
    """
    LedgerEntry.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        kind="nota_credito",
        amount=Decimal("8.00"),
        occurred_at=timezone.now(),
        cargo=cargo,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LedgerEntry.objects.create(
                shop=shop,
                customer=customer,
                user=user,
                kind="nota_credito",
                amount=Decimal("8.00"),
                occurred_at=timezone.now(),
                cargo=cargo,
            )
    assert LedgerEntry.objects.filter(kind="nota_credito").count() == 1

    # A plain credit note names no charge and is admitted.
    LedgerEntry.objects.create(
        shop=shop,
        customer=customer,
        user=user,
        kind="nota_credito",
        amount=Decimal("1.00"),
        occurred_at=timezone.now(),
    )
    assert LedgerEntry.objects.filter(kind="nota_credito").count() == 2


# ---------------------------------------------------------------------------
# 2.3 — the three immutable tables
# ---------------------------------------------------------------------------


def test_ledgerentry_cannot_be_updated(cargo):
    """`LedgerEntry` refuses an update (IC-01)."""
    with pytest.raises(LedgerImmutableError):
        cargo.amount = Decimal("99.00")
        cargo.save()
    cargo.refresh_from_db()
    assert cargo.amount == Decimal("10.00")


def test_ledgerentry_cannot_be_deleted(cargo):
    """`LedgerEntry` refuses a delete (IC-01)."""
    with pytest.raises(LedgerImmutableError):
        cargo.delete()
    assert LedgerEntry.objects.count() == 1


def test_cargolinea_cannot_be_updated_or_deleted(shop, cargo):
    """`CargoLinea` refuses an update and a delete (IC-09)."""
    producto = _producto(shop)
    linea = CargoLinea.objects.create(
        cargo=cargo,
        producto=producto,
        cantidad=Decimal("1"),
        precio_unitario=Decimal("1.20"),
        total=Decimal("1.20"),
    )
    with pytest.raises(LedgerImmutableError):
        linea.precio_unitario = Decimal("9.99")
        linea.save()
    with pytest.raises(LedgerImmutableError):
        linea.delete()
    assert CargoLinea.objects.count() == 1


def test_confirmacion_cannot_be_updated_or_deleted(cargo):
    """`Confirmacion` refuses an update and a delete (IC-01)."""
    confirmacion = Confirmacion.objects.create(
        cargo=cargo,
        estado="confirmado",
        confirmado_en=timezone.now(),
        origen="cliente",
    )
    with pytest.raises(LedgerImmutableError):
        confirmacion.nota = "corregida"
        confirmacion.save()
    with pytest.raises(LedgerImmutableError):
        confirmacion.delete()
    assert Confirmacion.objects.count() == 1


# ---------------------------------------------------------------------------
# 2.4 — no derived value is stored
# ---------------------------------------------------------------------------

# The field names design §3 forbids. A model that declares one of them
# stores a derived value, and a derived value goes stale the moment the
# next row is written.
FORBIDDEN_FIELD_NAMES = (
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
    "codigo",
)

# The names that would carry a confirmation state. No `Customer` field may
# hold one: the effective state is derived on read (IC-04).
FORBIDDEN_CONFIRMATION_NAMES = (
    "confirmado",
    "confirmacion",
    "confirmado_en",
    "estado_confirmacion",
    "confirmation_state",
)


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
    assert "prefix" not in customer_fields

    codigo_fields = {field.name for field in CustomerCodigo._meta.get_fields()}
    assert {"prefix", "codigo_hash", "issued_at", "issued_by", "revoked_at", "revoked_by"} <= codigo_fields


def test_the_throttle_ledger_stores_no_plaintext():
    """`CodigoIntento` records the hash of the presented credential only."""
    fields = {field.name for field in CodigoIntento._meta.get_fields()}
    assert "presented_hash" in fields
    assert not any("codigo" in name for name in fields)


def test_the_models_declare_no_derived_figure():
    """No model stores `caja`, `posicion_real` or an ageing bucket.

    The board's figures are recomputed on every read (CP-03, PA-03).
    """
    from django.apps import apps

    forbidden = {
        "caja",
        "posicion_real",
        "fiado_pendiente",
        "serie_caja",
        "existencias_registradas",
        "buckets",
        "bucket",
        "edad",
    }
    offences = []
    for model in apps.get_app_config("tienda").get_models():
        for field in model._meta.get_fields():
            if getattr(field, "name", "") in forbidden:
                offences.append(f"{model.__name__}.{field.name}")

    assert offences == [], (
        "A model stores a derived figure, which design §3 forbids: "
        + ", ".join(offences)
    )
