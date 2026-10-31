"""The data model of `fiado-confirmado` — design §3, extracted verbatim.

Every table lives in this module. Money is `Decimal(12,2)`, quantities
`Decimal(10,3)`, and instants are stored in UTC; the service layer converts
them to shop-local calendar days.

Three rules govern this file more than anything else:

* **Nothing derived is stored.** There is no `saldo`, no `status`, no `stock`,
  no `antiguedad_max_dias`, no `reconciled`, no `revisar`, no `precio_origen`
  and no confirmation state on a `cargo` or on a `Customer`. Every figure the
  board shows is recomputed on read from these rows.
* **Three tables are append-only.** `LedgerEntry`, `CargoLinea` and
  `Confirmacion` refuse an update and refuse a delete. A correction is
  appended, never edited.
* **The credential is not a column of `Customer`.** `CustomerCodigo` holds
  the `prefix`, the hash and the revocation record.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import BooleanField, DecimalField, Q
from django.db.models.expressions import CombinedExpression
from django.db.models.functions import Round

# The vocabulary of `LedgerEntry.kind`. The service validates the kind before
# writing (rule 17 -> `tipo_desconocido`); this `CHECK` is the backstop under
# a race, so an unknown kind can never reach the table.
LEDGER_ENTRY_KINDS = ("cargo", "pago", "nota_credito")

# The vocabulary of `CashMovement.kind` and `StockMovement.kind`.
MOVEMENT_KINDS = ("entrada", "salida")

# The vocabulary of `Confirmacion.estado`. A charge holds at most one row per
# state, for the whole life of the charge.
CONFIRMATION_STATES = ("confirmado", "en_disputa")

# The vocabulary of `Confirmacion.origen`. `facilitado` is the only origin
# that names a facilitator.
CONFIRMATION_ORIGINS = ("cliente", "dueno", "facilitado")


class LedgerImmutableError(ValidationError):
    """Raised when an append-only row is about to be updated or deleted.

    `LedgerEntry`, `CargoLinea` and `Confirmacion` are append-only: a
    correction is appended as a `nota de crédito`, so the original rows are
    never rewritten (IC-01, IC-09).
    """


class AppendOnlyQuerySet(models.QuerySet):
    """A queryset that refuses to update or to delete an existing row.

    The model guard covers `instance.save()` and `instance.delete()`, but
    `QuerySet.update()` and `QuerySet.delete()` bypass both of them and
    would happily rewrite or remove an append-only row. Design §3 says these
    three tables are append-only, so the queryset closes the same hole.
    """

    def update(self, **kwargs):
        raise LedgerImmutableError(
            f"{self.model.__name__} is append-only: a row cannot be "
            "updated. Append a new row instead."
        )

    def delete(self):
        raise LedgerImmutableError(
            f"{self.model.__name__} is append-only: a row cannot be "
            "deleted. Append a correcting row instead."
        )


class AppendOnlyModel(models.Model):
    """Base class of the three immutable tables.

    `save()` refuses an update and `delete()` refuses a removal. Creating a
    row is the only permitted write.

    The guard reads `_state.adding`, Django's own flag for "this instance has
    not been persisted yet". Checking the primary key instead would be
    wrong in both directions: a row loaded from the database and modified in
    place would slip through when its pk was still unset, and a row whose
    pk was assigned by hand before its first write would be refused.
    """

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise LedgerImmutableError(
                f"{self.__class__.__name__} is append-only: a row cannot be "
                "updated. Append a new row instead."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LedgerImmutableError(
            f"{self.__class__.__name__} is append-only: a row cannot be "
            "deleted. Append a correcting row instead."
        )


class Shop(models.Model):
    """The shop. Every other row hangs off exactly one shop."""

    name = models.CharField(max_length=200, unique=True)
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="EUR")
    is_demo = models.BooleanField(default=False)
    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="shops",
        blank=True,
    )

    class Meta:
        db_table = "tienda_shop"

    def __str__(self):
        return self.name


class Customer(models.Model):
    """A customer of the shop — the owner's own record and policy.

    The derived state (`suspendido` or not, and the reason) is **never
    stored**: it is computed on read from the ledger rows and the ageing
    (D1). Only the owner's own acts are recorded here — the alias, the phone,
    the credit limit, and the suspension override.
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="customers")
    alias = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, blank=True, null=True)
    # NULL means "no limit" (sin limite). A value is always >= 0.
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    # The override records an act (the owner lifted the automatic
    # suspension), never a derived value.
    suspended_override_at = models.DateTimeField(blank=True, null=True)
    suspended_override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="suspension_overrides_given",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "tienda_customer"
        constraints = [
            # UNIQUE (shop_id, alias) — the alias identifies a customer
            # inside its shop, not across shops.
            models.UniqueConstraint(
                fields=["shop", "alias"], name="uniq_customer_shop_alias"
            ),
            # A credit limit is either absent (no limit) or non-negative.
            models.CheckConstraint(
                condition=models.Q(credit_limit__isnull=True) | models.Q(credit_limit__gte=0),
                name="chk_customer_credit_limit_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.alias} ({self.shop_id})"


class LedgerEntry(AppendOnlyModel):
    """One movement of the credit book — a `cargo`, a `pago` or a
    `nota_credito`. The table is append-only.

    `cargo_id` is set **only** by a credit note that reconciles a dispute; a
    plain credit note that reduces the outstanding without touching a charge
    omits it. The partial unique index admits one reconciling credit note per
    charge, for the whole life of the charge (rule 5).
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="ledger_entries")
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    # The author of the entry. A client never writes to the ledger directly.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    kind = models.CharField(max_length=20, choices=[(k, k) for k in LEDGER_ENTRY_KINDS])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    occurred_at = models.DateTimeField()
    # The charge this credit note reconciles. NULL for every other kind.
    cargo = models.ForeignKey(
        "LedgerEntry",
        on_delete=models.PROTECT,
        related_name="reconciliations",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_ledgerentry"
        constraints = [
            # An amount is always strictly positive (rule 16).
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="chk_ledgerentry_amount_positive"
            ),
            # The kind belongs to the vocabulary (rule 17).
            models.CheckConstraint(
                condition=models.Q(kind__in=LEDGER_ENTRY_KINDS),
                name="chk_ledgerentry_kind_vocabulary",
            ),
            # A credit note that names a charge reconciles it; a plain credit
            # note does not touch a charge.
            models.CheckConstraint(
                condition=(
                    models.Q(kind="nota_credito")
                    | models.Q(cargo__isnull=True)
                ),
                name="chk_ledgerentry_cargo_only_on_credit_note",
            ),
            # Partial UNIQUE (cargo_id) WHERE kind='nota_credito' — a charge is
            # reconciled at most once, for the whole life of the charge.
            models.UniqueConstraint(
                fields=["cargo"],
                condition=Q(kind="nota_credito", cargo__isnull=False),
                name="uniq_ledgerentry_one_reconciliation_per_cargo",
            ),
        ]

    def __str__(self):
        return f"{self.kind} {self.amount}"


class CashMovement(models.Model):
    """A movement of the drawer — an `entrada` or a `salida`.

    `occurred_at` is server-stamped and never client-supplied: a request that
    carries it is refused with `campo_no_admitido` (rule 4), and the server
    refuses a stamp in the future (rule 13).
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="cash_movements")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_movements"
    )
    kind = models.CharField(max_length=20, choices=[(k, k) for k in MOVEMENT_KINDS])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    concept = models.CharField(max_length=300)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_cashmovement"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="chk_cashmovement_amount_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=MOVEMENT_KINDS),
                name="chk_cashmovement_kind_vocabulary",
            ),
        ]

    def __str__(self):
        return f"{self.kind} {self.amount}"


class DayClose(models.Model):
    """The close of a day — the only instrument that measures the shop's
    money.

    `esperado` is the server-computed `caja` at close time and `desviacion`
    is the server-computed `esperado - contado`. Neither is client-supplied:
    a close request that carries either is refused with `campo_no_admitido`
    (rule 15), and an `esperado` that disagrees with the derived figure is
    refused outright (rule 14).
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="day_closes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="day_closes"
    )
    date = models.DateField()
    esperado = models.DecimalField(max_digits=12, decimal_places=2)
    contado = models.DecimalField(max_digits=12, decimal_places=2)
    desviacion = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_dayclose"
        constraints = [
            # UNIQUE (shop_id, date) — a day is closed once per shop
            # (rule 8).
            models.UniqueConstraint(fields=["shop", "date"], name="uniq_dayclose_shop_date"),
            models.CheckConstraint(
                condition=models.Q(esperado__gte=0), name="chk_dayclose_esperado_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(contado__gte=0), name="chk_dayclose_contado_non_negative"
            ),
        ]

    def __str__(self):
        return f"{self.shop_id} {self.date}"


class Producto(models.Model):
    """A catalogue item.

    The catalogue holds the *current* price. The price actually charged is
    frozen in the `CargoLinea` as `precio_unitario`, so a later catalogue
    change never rewrites a stored line (IC-08).
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="productos")
    nombre = models.CharField(max_length=200)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    unidad = models.CharField(max_length=32, default="unidad")
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "tienda_producto"
        constraints = [
            # UNIQUE (shop_id, nombre) — a name identifies an item inside its
            # shop.
            models.UniqueConstraint(
                fields=["shop", "nombre"], name="uniq_producto_shop_nombre"
            ),
            models.CheckConstraint(
                condition=models.Q(precio__gte=0), name="chk_producto_precio_non_negative"
            ),
        ]

    def __str__(self):
        return self.nombre


class CargoLinea(AppendOnlyModel):
    """One itemised line of a `cargo`. The table is append-only.

    `precio_unitario` is the price actually charged at the moment of the
    charge — the catalogue price unless the owner overrode it — and `total`
    is the line's own total. The `CHECK` below is the per-row half of the
    cross-row check of rule 3: it keeps a line from disagreeing with itself,
    while the service compares the declared amount against the sum of the
    lines inside the write transaction.
    """

    cargo = models.ForeignKey(
        LedgerEntry, on_delete=models.CASCADE, related_name="lineas"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="lineas"
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "tienda_cargolinea"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0), name="chk_cargolinea_cantidad_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(precio_unitario__gte=0),
                name="chk_cargolinea_precio_non_negative",
            ),
            # total = round(cantidad * precio_unitario, 2)
            #
            # The comparison is built with a `CombinedExpression`, not with
            # the `==` operator on two `Round` expressions. Django's
            # `Expression.__eq__` compares identity, so `Round(a) == Round(b)`
            # evaluates to the Python `False` at import time and the CHECK
            # would silently become a constant. `CombinedExpression` keeps
            # both sides as SQL and emits the comparison as SQL.
            models.CheckConstraint(
                condition=Q(
                    CombinedExpression(
                        Round(
                            models.F("total"),
                            2,
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        ),
                        "=",
                        Round(
                            models.F("cantidad") * models.F("precio_unitario"),
                            2,
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        ),
                        output_field=BooleanField(),
                    )
                ),
                name="chk_cargolinea_total_matches_line",
            ),
        ]

    def __str__(self):
        return f"{self.cantidad} x {self.precio_unitario}"


class Confirmacion(AppendOnlyModel):
    """One confirmation or dispute about a `cargo`. The table is append-only.

    The row points at the `LedgerEntry` of the charge it ratifies through
    `cargo_id` — the charge this row ratifies. It is **not** the
    `cargo_id` of the `LedgerEntry` table, which is a different column on a
    different table.

    A charge holds at most one `confirmado` row and at most one `en_disputa`
    row, for the whole life of the charge — the two partial unique indexes
    below. A charge that goes `confirmado -> en_disputa` therefore holds two
    rows with different states, and a charge that tries to reach the same
    state twice violates its index (rules 6 and 7).
    """

    cargo = models.ForeignKey(
        LedgerEntry, on_delete=models.PROTECT, related_name="confirmaciones"
    )
    estado = models.CharField(max_length=20, choices=[(s, s) for s in CONFIRMATION_STATES])
    importe_reclamado = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    nota = models.TextField(blank=True, null=True)
    confirmado_en = models.DateTimeField(blank=True, null=True)
    origen = models.CharField(
        max_length=20, choices=[(o, o) for o in CONFIRMATION_ORIGINS], default="cliente"
    )
    # The user who facilitated the confirmation. Only set for the origin
    # `facilitado`.
    facilitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmaciones_facilitadas",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_confirmacion"
        constraints = [
            # `confirmado` carries the instant and claims no amount;
            # `en_disputa` claims an amount and carries no instant.
            models.CheckConstraint(
                condition=(
                    models.Q(estado="confirmado")
                    | (
                        models.Q(estado="en_disputa")
                        & models.Q(confirmado_en__isnull=True)
                        & models.Q(importe_reclamado__isnull=False)
                    )
                ),
                name="chk_confirmacion_state_fields",
            ),
            # `confirmado` implies `confirmado_en IS NOT NULL` and
            # `importe_reclamado IS NULL`.
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado="confirmado")
                    | (
                        models.Q(confirmado_en__isnull=False)
                        & models.Q(importe_reclamado__isnull=True)
                    )
                ),
                name="chk_confirmacion_confirmado_fields",
            ),
            # `origen='facilitado'` if and only if `facilitado_por_id` is set.
            models.CheckConstraint(
                condition=(
                    models.Q(origen="facilitado", facilitado_por__isnull=False)
                    | ~models.Q(origen="facilitado")
                )
                & (
                    models.Q(origen__in=CONFIRMATION_ORIGINS)
                ),
                name="chk_confirmacion_facilitador_iff_origen",
            ),
            # The amount claimed in a dispute is never negative.
            models.CheckConstraint(
                condition=models.Q(importe_reclamado__isnull=True)
                | models.Q(importe_reclamado__gte=0),
                name="chk_confirmacion_importe_non_negative",
            ),
            # Partial UNIQUE (cargo_id) WHERE estado='confirmado' — at most
            # one confirmation per charge, for the whole life of the charge.
            models.UniqueConstraint(
                fields=["cargo"],
                condition=Q(estado="confirmado"),
                name="uniq_confirmacion_one_confirmado_per_cargo",
            ),
            # Partial UNIQUE (cargo_id) WHERE estado='en_disputa' — at most
            # one dispute per charge, for the whole life of the charge.
            models.UniqueConstraint(
                fields=["cargo"],
                condition=Q(estado="en_disputa"),
                name="uniq_confirmacion_one_disputa_per_cargo",
            ),
        ]

    def __str__(self):
        return f"{self.estado} {self.cargo_id}"


class StockMovement(models.Model):
    """A recorded movement of a product — an `entrada` or a `salida`.

    Conditional (Regla 6): the table exists only while the stock ceiling is
    in scope. `existencias_registradas` is derived from these rows on read;
    no field named `stock` exists, and no rule, price, limit or suspension
    depends on the figure (CP-07).

    `occurred_at` is server-stamped and never client-supplied (rule 4).
    """

    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="movimientos"
    )
    kind = models.CharField(max_length=20, choices=[(k, k) for k in MOVEMENT_KINDS])
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    concept = models.CharField(max_length=300)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_stockmovement"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0),
                name="chk_stockmovement_cantidad_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=MOVEMENT_KINDS),
                name="chk_stockmovement_kind_vocabulary",
            ),
        ]

    def __str__(self):
        return f"{self.kind} {self.cantidad}"


class CustomerCodigo(models.Model):
    """The credential of a customer — the `codigo` the client presents.

    The credential is **not** a column of `Customer`: it lives here, so that
    the plaintext can be rotated without touching the customer's own record.
    Only the hash is stored; the plaintext is shown once, at issue time.

    `prefix` is the six-character non-secret head of the credential. It is
    unique per shop, and a customer holds at most one **active** credential
    at a time — the partial unique index admits a second row only once the
    first one is revoked (rule 9).
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="codigos")
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="codigos"
    )
    prefix = models.CharField(max_length=6)
    codigo_hash = models.CharField(max_length=255)
    issued_at = models.DateTimeField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="codigos_issued",
    )
    revoked_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="codigos_revoked",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_customercodigo"
        constraints = [
            # UNIQUE (shop_id, prefix) — the prefix identifies a credential
            # inside its shop (rule 9).
            models.UniqueConstraint(fields=["shop", "prefix"], name="uniq_codigo_shop_prefix"),
            # A revocation records an act, so it always names the author.
            models.CheckConstraint(
                condition=models.Q(revoked_at__isnull=True)
                | models.Q(revoked_by__isnull=False),
                name="chk_codigo_revocation_has_author",
            ),
            # Partial UNIQUE (customer_id) WHERE revoked_at IS NULL — one
            # active credential per customer.
            models.UniqueConstraint(
                fields=["customer"],
                condition=Q(revoked_at__isnull=True),
                name="uniq_codigo_one_active_per_customer",
            ),
        ]

    def __str__(self):
        return f"{self.prefix} ({self.customer_id})"


class CodigoIntento(models.Model):
    """The append-only throttle ledger — every presented credential.

    The row holds the source address, the hash of the presented credential
    and the instant. It never holds the plaintext: the hash is what is
    compared, so the throttle ledger cannot leak a credential.
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="codigo_intentos")
    source_ip = models.GenericIPAddressField()
    presented_hash = models.CharField(max_length=255)
    at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_codigointento"
        indexes = [
            models.Index(fields=["shop", "at"], name="idx_codigointento_shop_at"),
            models.Index(
                fields=["shop", "presented_hash"], name="idx_codigointento_shop_hash"
            ),
        ]

    def __str__(self):
        return f"{self.source_ip} @ {self.at}"
