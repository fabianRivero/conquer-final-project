"""The data model of `fiado-confirmado` — design §3, extracted verbatim.

Every table lives in this module. Money is `Decimal(12,2)`, quantities
`Decimal(10,3)`, and instants are stored in UTC; the service layer converts
them to shop-local calendar days.

Four rules govern this file more than anything else:

* **Nothing derived is stored.** There is no `saldo`, no `status`, no `stock`,
  no `antiguedad_max_dias`, no `reconciled`, no `revisar`, no `precio_origen`,
  no `pagado`, no `importe_reclamado` and no confirmation state on a `cargo`
  or on a `Customer`. Every figure the board shows is recomputed on read from
  these rows.
* **Five tables are append-only.** `LedgerEntry`, `CargoLinea`,
  `Confirmacion`, `PropuestaLinea` and `ImputacionPago` refuse an update and
  refuse a delete. A correction is appended, never edited.
* **The credential is not a column of `Customer`.** `CustomerCodigo` holds
  the `prefix`, the hash and the revocation record.
* **A customer never holds a credit.** A `pago` never exceeds the debt it
  retires (rule 19): the shop returns the excess as change and it never
  enters the book. There is no field, anywhere, that holds a balance in the
  client's favour.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import BooleanField, DecimalField, Q
from django.db.models.expressions import CombinedExpression
from django.db.models.functions import Round

# The vocabulary of `LedgerEntry.kind`. The service validates the kind before
# writing (rule 16 -> `tipo_desconocido`); this `CHECK` is the backstop under
# a race, so an unknown kind can never reach the table.
#
# There are **two** kinds. The third one the v1 model carried — `nota_credito`
# — is gone with the dispute machinery: the client confirms the charge before
# it exists, so there is nothing to reconcile afterwards.
LEDGER_ENTRY_KINDS = ("cargo", "pago")

# The vocabulary of `CashMovement.kind` and `StockMovement.kind`.
MOVEMENT_KINDS = ("entrada", "salida")

# The vocabulary of `Confirmacion.estado`. **One state only**: a charge
# either carries its confirmation or it does not exist. There is no
# `en_disputa`, so there is no second row per charge either.
CONFIRMATION_STATES = ("confirmado",)

# The vocabulary of `Confirmacion.origen`. The origin says **what kind of
# act** the confirmation was - the owner recorded it, or a `dependiente` did -
# and `confirmado_por` says **who** did it, always.
#
# The vocabulary changed when the N5 gate opened. It used to carry
# `facilitado`, which named a **third actor**: someone presenting at the
# counter a charge somebody else had prepared. That actor does not exist in
# the v2 model - the client confirms on their own screen and there is no route
# where the two principals meet - so the word described nothing that could
# happen, and the name of the actor now lives in its own column, where it is
# always present.
#
# The origin is **inferred by the server** from the acting session, never
# taken from the request body (rule 7b).
CONFIRMATION_ORIGINS = ("tienda", "dependiente")

# The vocabulary of `FiadoPropuesto.estado`. The proposal moves from
# `pendiente` to exactly one of `confirmado` or `cancelado`, never back.
PROPUESTA_ESTADOS = ("pendiente", "confirmado", "cancelado")

# The vocabulary of `PagoPropuesto.estado`. The proposal moves from
# `pendiente` to exactly one of `validado` or `rechazado`, never back.
PAGO_PROPUESTO_ESTADOS = ("pendiente", "validado", "rechazado")


class LedgerImmutableError(ValidationError):
    """Raised when an append-only row is about to be updated or deleted.

    `LedgerEntry`, `CargoLinea`, `Confirmacion`, `PropuestaLinea` and
    `ImputacionPago` are append-only: a correction is appended as a new row,
    so the original rows are never rewritten (IC-01, IC-09).
    """


class AppendOnlyQuerySet(models.QuerySet):
    """A queryset that refuses to update or to delete an existing row.

    The model guard covers `instance.save()` and `instance.delete()`, but
    `QuerySet.update()` and `QuerySet.delete()` bypass both of them and
    would happily rewrite or remove an append-only row. Design §3 says these
    tables are append-only, so the queryset closes the same hole.
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
    """Base class of the immutable tables.

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
    the credit limit, the suspension override and who registered the customer.

    There is no field here that holds a balance in the customer's favour: a
    `pago` never exceeds the debt it retires, so no credit can exist
    (ADR-26, rule 19).
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="customers")
    # The staff member who registered the customer. NULL when the customer
    # predates the register.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customers_registered",
        blank=True,
        null=True,
    )
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


class Producto(models.Model):
    """A catalogue item.

    The catalogue holds the *current* price. The price actually charged is
    frozen in the `CargoLinea` — and in the `PropuestaLinea` — as
    `precio_unitario`, so a later catalogue change never rewrites a stored
    line (IC-08).
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


class FiadoPropuesto(models.Model):
    """A prepared figure — a `fiado` the owner is offering, not yet a debt.

    **A proposal is not a scope and not an obligation.** It carries a
    `customer` because it is *about* a customer — the reference, not the
    authority. While it is `pendiente` it moves no balance and it is not a
    debt: the outstanding does not change until the confirmation.

    The rows are mutable, and only in their own lifecycle: `estado`,
    `confirmed_at`, `canceled_at`. The move is one-way — `pendiente` to
    exactly one of `confirmado` or `cancelado`, never back (rule 7).

    `user` is the **preparer**, and it is also the **ownership**: with the
    N5 gate open, a `dependiente` confirms and cancels only the proposals
    it prepared. Nobody confirms somebody else's.
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="propuestas")
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="propuestas"
    )
    # The staff member who prepared the proposal.
    #
    # This column is also the **ownership**: a `dependiente` confirms and
    # cancels only the proposals it prepared, and `user` is what makes that
    # filter possible.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="propuestas_preparadas"
    )
    estado = models.CharField(
        max_length=20, choices=[(e, e) for e in PROPUESTA_ESTADOS], default="pendiente"
    )
    # The declared total. The write path checks it against the sum of the
    # proposal's own lines inside the transaction (rule 3).
    total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    canceled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "tienda_fiadopropuesto"
        constraints = [
            # The state belongs to the vocabulary.
            models.CheckConstraint(
                condition=models.Q(estado__in=PROPUESTA_ESTADOS),
                name="chk_fiadopropuesto_estado_vocabulary",
            ),
            # `confirmado` implies `confirmed_at IS NOT NULL` and
            # `cancelado` implies `canceled_at IS NOT NULL`. The two are
            # mutually exclusive.
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado="confirmado")
                    | (
                        models.Q(confirmed_at__isnull=False)
                        & models.Q(canceled_at__isnull=True)
                    )
                ),
                name="chk_fiadopropuesto_confirmado_fields",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado="cancelado")
                    | (
                        models.Q(canceled_at__isnull=False)
                        & models.Q(confirmed_at__isnull=True)
                    )
                ),
                name="chk_fiadopropuesto_cancelado_fields",
            ),
            # The total is never negative.
            models.CheckConstraint(
                condition=models.Q(total__gte=0), name="chk_fiadopropuesto_total_non_negative"
            ),
        ]

    def __str__(self):
        return f"{self.estado} {self.total} ({self.customer_id})"


class PropuestaLinea(AppendOnlyModel):
    """One itemised line of a `FiadoPropuesto`. The table is append-only.

    A proposal's line is the mirror of a charge's line: the same fields, the
    same arithmetic, the same snapshot semantics. `precio_unitario` is the
    price offered at the moment the proposal was prepared, and `total` is the
    line's own total.

    The `CHECK` below is the per-row half of the cross-row check of rule 3:
    it keeps a line from disagreeing with itself, while the service compares
    the declared total against the sum of the lines inside the write
    transaction.
    """

    propuesta = models.ForeignKey(
        FiadoPropuesto, on_delete=models.CASCADE, related_name="lineas"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="lineas_propuesta"
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "tienda_propuestalinea"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0),
                name="chk_propuestalinea_cantidad_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(precio_unitario__gte=0),
                name="chk_propuestalinea_precio_non_negative",
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
                name="chk_propuestalinea_total_matches_line",
            ),
        ]

    def __str__(self):
        return f"{self.cantidad} x {self.precio_unitario}"


class LedgerEntry(AppendOnlyModel):
    """One movement of the credit book — a `cargo` or a `pago`. The table is
    append-only.

    There is **no `cargo_id`** on this table any more. The v1 column existed
    only so a `nota de crédito` could name the charge it reconciled; with the
    dispute machinery gone there is nothing to reconcile, and a charge's
    repayment is recorded in `ImputacionPago` instead.
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_ledgerentry"
        constraints = [
            # An amount is always strictly positive (rule 15).
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="chk_ledgerentry_amount_positive"
            ),
            # The kind belongs to the vocabulary (rule 16). The vocabulary has
            # two values: `cargo` and `pago`. `nota_credito` was removed with
            # the dispute machinery.
            models.CheckConstraint(
                condition=models.Q(kind__in=LEDGER_ENTRY_KINDS),
                name="chk_ledgerentry_kind_vocabulary",
            ),
        ]

    def __str__(self):
        return f"{self.kind} {self.amount}"


class CargoLinea(AppendOnlyModel):
    """One itemised line of a `cargo`. The table is append-only.

    `precio_unitario` is the price actually charged at the moment of the
    charge — the catalogue price unless the owner overrode it — and `total`
    is the line's own total. The `CHECK` below is the per-row half of the
    cross-row check of rule 3: it keeps a line from disagreeing with itself,
    while the service compares the declared amount against the sum of the
    lines inside the write transaction.

    The itemisation is **mandatory**: a charge without lines cannot exist,
    because a figure the client cannot see broken down is not a figure the
    client confirmed (IC-07).
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
    """One confirmation of a `cargo`. The table is append-only.

    The row points at the `LedgerEntry` of the charge it ratifies through
    `cargo_id` — the charge this row ratifies.

    **There is one state only: `confirmado`.** The v1 model carried a second
    one, `en_disputa`, and with it the `importe_reclamado`, the `nota` field
    and two partial unique indexes. All of that is gone: the client confirms
    the charge before it exists, so there is nothing to disagree about
    afterwards (ADR-18, ADR-19).

    A charge therefore holds at most one row, for the whole life of the
    charge — the partial unique index below.
    """

    cargo = models.ForeignKey(
        LedgerEntry, on_delete=models.PROTECT, related_name="confirmaciones"
    )
    estado = models.CharField(max_length=20, choices=[(s, s) for s in CONFIRMATION_STATES])
    confirmado_en = models.DateTimeField()
    # The origin is inferred by the server from the acting session, never
    # read from the request body (rule 7b).
    origen = models.CharField(
        max_length=20, choices=[(o, o) for o in CONFIRMATION_ORIGINS], default="tienda"
    )
    # The user who recorded the confirmation. **Always set** - the row says
    # who acted, and it says it without a condition on the origin.
    #
    # The column replaced `facilitado_por`, which named a third actor that
    # the v2 model does not have. With the N5 gate open there are only two
    # actors - the owner and the `dependiente` - and both of them record
    # confirmations, so the name belongs here and nowhere else.
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmaciones_registradas",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tienda_confirmacion"
        constraints = [
            # The state belongs to the vocabulary, and the vocabulary has one
            # value only.
            models.CheckConstraint(
                condition=models.Q(estado__in=CONFIRMATION_STATES),
                name="chk_confirmacion_estado_vocabulary",
            ),
            # Partial UNIQUE (cargo_id) WHERE estado='confirmado' — at most
            # one confirmation per charge, for the whole life of the charge.
            models.UniqueConstraint(
                fields=["cargo"],
                condition=Q(estado="confirmado"),
                name="uniq_confirmacion_one_confirmado_per_cargo",
            ),
        ]

    def __str__(self):
        return f"{self.estado} {self.cargo_id}"


class ImputacionPago(AppendOnlyModel):
    """One (payment, charge) pair — how much of a charge a payment settled.

    This table is where the repartition of a payment lives. A `pago` of
    20,00 € that retires a charge of 8,00 €, one of 7,00 € and 5,00 € of a
    third is **one** `LedgerEntry` and **three** rows here: 8,00, 7,00 and
    5,00. The owner's charges then read 8/8, 7/7 and 5/15.

    **The grain is the charge**, not the line. A charge of 15,00 € made of
    three `CargoLinea` rows is one debt of 15,00 €, and a payment that
    settles 5,00 € of it writes one row of 5,00 € against the charge.

    The table is append-only, and there is deliberately **no `pagado` column
    on a charge**: a mutable column would break the append-only guarantee of
    the book and would be a stored derived value, which design §3.1 forbids
    and landmine 12 polices. The remaining balance of a charge is derived on
    read as `cargo.amount - SUM(ImputacionPago.importe)` over its rows
    (ADR-27).
    """

    # The payment that brought the money. Its `kind` is `pago` (rule 20).
    pago = models.ForeignKey(
        LedgerEntry, on_delete=models.PROTECT, related_name="imputaciones"
    )
    # The charge the payment retires. Its `kind` is `cargo` (rule 20).
    cargo = models.ForeignKey(
        LedgerEntry, on_delete=models.PROTECT, related_name="imputado_por"
    )
    importe = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "tienda_imputacionpago"
        constraints = [
            # An imputation always places something.
            models.CheckConstraint(
                condition=models.Q(importe__gt=0), name="chk_imputacionpago_importe_positive"
            ),
            # UNIQUE (pago_id, cargo_id) — one payment cannot touch the same
            # charge twice.
            models.UniqueConstraint(
                fields=["pago", "cargo"], name="uniq_imputacionpago_pago_cargo"
            ),
        ]

    def __str__(self):
        return f"{self.importe} -> cargo {self.cargo_id}"


class PagoPropuesto(models.Model):
    """The client's request that the owner record a payment.

    **A proposed payment is a request, not a scope.** It creates no
    `LedgerEntry`, it moves no balance, and it grants the client nothing
    beyond the acknowledgement that it was received. The `pago` itself is a
    separate `LedgerEntry` appended by the owner, so the credit book stays
    append-only even though the request that preceded it is not.

    **It names no charge.** The client proposes an amount and the FIFO
    decides which debts it retires; the decision is recorded in
    `ImputacionPago` when the owner validates the proposal (ADR-27).

    The rows are mutable, and only in their own lifecycle: `estado`,
    `resolved_at` and `resolved_by_id`. The move is one-way — `pendiente` to
    exactly one of `validado` or `rechazado`, never back (rule 18).
    """

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="pagos_propuestos")
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="pagos_propuestos"
    )
    # The owner who validated or rejected the proposal. NULL while the
    # proposal is pending.
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pagos_propuestos_resueltos",
        blank=True,
        null=True,
    )
    importe = models.DecimalField(max_digits=12, decimal_places=2)
    # The client's own words about their payment — a reference, not proof.
    # The `comprobante` attachment is a planned extension and is not
    # implemented (ADR-25).
    referencia = models.TextField(blank=True)
    estado = models.CharField(
        max_length=20,
        choices=[(e, e) for e in PAGO_PROPUESTO_ESTADOS],
        default="pendiente",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "tienda_pagopropuesto"
        constraints = [
            # The state belongs to the vocabulary.
            models.CheckConstraint(
                condition=models.Q(estado__in=PAGO_PROPUESTO_ESTADOS),
                name="chk_pagopropuesto_estado_vocabulary",
            ),
            # The amount is always strictly positive (rule 17).
            models.CheckConstraint(
                condition=models.Q(importe__gt=0), name="chk_pagopropuesto_importe_positive"
            ),
            # `validado` and `rechazado` both imply `resolved_at IS NOT NULL`
            # and `resolved_by_id IS NOT NULL` — the owner's decision is an
            # act and it always names who took it.
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado="pendiente")
                    | (
                        models.Q(resolved_at__isnull=True)
                        & models.Q(resolved_by__isnull=True)
                    )
                ),
                name="chk_pagopropuesto_pendiente_fields",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado__in=("validado", "rechazado"))
                    | (
                        models.Q(resolved_at__isnull=False)
                        & models.Q(resolved_by__isnull=False)
                    )
                ),
                name="chk_pagopropuesto_resolved_fields",
            ),
        ]

    def __str__(self):
        return f"{self.estado} {self.importe} ({self.customer_id})"


class CashMovement(models.Model):
    """A movement of the drawer — an `entrada` or a `salida`.

    `occurred_at` is server-stamped and never client-supplied: a request that
    carries it is refused with `campo_no_admitido` (rule 4), and the server
    refuses a stamp in the future (rule 12).
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
    (rule 14), and an `esperado` that disagrees with the derived figure is
    refused outright (rule 13).
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
            # (rule 9).
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
    first one is revoked (rule 10).
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
            # inside its shop (rule 10).
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


#: The tables of the demo dataset.
#:
#: A table either carries the shop's id itself - `shop_id` - or hangs
#: off a row that carries it. The second kind is deleted by the ids of
#: its parents, and it goes BEFORE them.
#:
#: The path is resolved from the SCHEMA rather than written by hand: the
#: foreign keys are read from the PostgreSQL catalog and walked until the
#: shop is reached. A table that the walk cannot reach has nothing to do
#: with the demo, and it is left alone.
def _claves_foraneas(cursor):
    """The foreign keys of the application's tables, read from the catalog.

    Returns the mapping `tabla -> [(columna, tabla_referenciada)]`.

    The read is over `pg_constraint` and not over `information_schema`:
    the `constraint_column_usage` view returns no row for some foreign
    keys, and a seed that discovers no tables deletes nothing at all.
    """
    cursor.execute(
        """
        SELECT hijo.relname, padre.relname,
               (SELECT a.attname
                  FROM pg_attribute a
                 WHERE a.attrelid = con.conrelid
                   AND a.attnum = con.conkey[1]) AS columna
        FROM pg_constraint con
        JOIN pg_class hijo ON hijo.oid = con.conrelid
        JOIN pg_class padre ON padre.oid = con.confrelid
        WHERE con.contype = 'f'
          AND hijo.relname LIKE 'tienda_%%'
        """
    )
    claves = {}
    for tabla, referencia, columna in cursor.fetchall():
        claves.setdefault(tabla, []).append((columna, referencia))
    return claves


def _tablas_del_demo(cursor):
    """The tables that hang off a shop, read from the schema.

    The set is closed by walking the foreign keys out from the shop, so
    a table added to the model later is deleted by the seed without the
    seed being edited.
    """
    claves = _claves_foraneas(cursor)
    hijos = {}
    for tabla, relaciones in claves.items():
        for _, referencia in relaciones:
            if not referencia.startswith("auth_"):
                hijos.setdefault(referencia, []).append(tabla)

    vistas = set()
    pendientes = ["tienda_shop"]
    while pendientes:
        tabla = pendientes.pop()
        for hija in sorted(set(hijos.get(tabla, []))):
            if hija not in vistas:
                vistas.add(hija)
                pendientes.append(hija)
    return vistas, claves


def _camino_mas_largo(tabla, claves, vista=None):
    """The LONGEST path from a table to the shop.

    `None` when the table does not reach the shop at all.

    The longest path is the one that matters for the capture: a table
    whose ids are read through a parent needs that parent's ids first,
    and the parent's ids are read through ITS parent. The shortest path
    would not tell the order.
    """
    if tabla == "tienda_shop":
        return 0
    if vista is None:
        vista = set()
    if tabla in vista:
        return None
    vista = vista | {tabla}

    mejor = None
    for _, referencia in claves.get(tabla, []):
        if referencia.startswith("auth_"):
            continue
        sub = _camino_mas_largo(referencia, claves, vista)
        if sub is not None:
            largo = sub + 1
            mejor = largo if mejor is None else max(mejor, largo)
    return mejor


def _profundidad(tabla, claves, vista=None):
    """How many steps a table is from the shop.

    `None` when the table does not reach the shop at all.
    """
    if tabla == "tienda_shop":
        return 0
    if vista is None:
        vista = set()
    if tabla in vista:
        return None
    vista = vista | {tabla}

    mejor = None
    for _, referencia in claves.get(tabla, []):
        if referencia.startswith("auth_"):
            continue
        sub = _profundidad(referencia, claves, vista)
        if sub is not None:
            profundidad = sub + 1
            mejor = (
                profundidad if mejor is None else min(mejor, profundidad)
            )
    return mejor


def borrar_dataset_demo() -> int:
    """Delete the demo dataset. **The only deletion in the codebase.**

    The seed needs to be able to CHANGE its dataset - a new catalogue, a
    new figure - and the only way to change a dataset is to remove the
    old one. The append-only guard is absolute everywhere else, so this
    function is the one and only way through it, and it lives here so
    that there is exactly ONE place in the codebase that can remove an
    append-only row.

    **It is confined to `is_demo=True`.** The shop is looked up by the
    flag and not by a name or an id, and every statement filters on the
    shop's id, so the function cannot reach a real shop even by
    mistake.

    **It goes underneath the ORM, on purpose.** Django emulates
    CASCADE in the ORM and writes `NO ACTION` in the schema, so the
    database has no cascade to offer. The append-only guard is an
    ORM-level guard - the schema has no trigger and no rule against
    removing these rows - and this function is the one caller that goes
    underneath it. It is the seed, a maintenance tool that rebuilds a
    dataset which is nobody's real book.

    **The ids are captured before anything is deleted.** A table that
    hangs off another one is found by its parent's ids, and those ids
    have to be read while the parent rows are still there. The capture
    is therefore a pass of its own, and the deletion is a second pass
    that works from the captured ids - so the order of the DELETIONS
    does not matter, which is what `DEFERRABLE INITIALLY DEFERRED`
    allows.

    The tables are discovered from the SCHEMA, by walking the foreign
    keys out from the shop, so a table added to the model later is
    deleted by the seed without the seed being edited.

    It returns the number of shops removed.
    """
    from django.db import connection

    ids = list(Shop.objects.filter(is_demo=True).values_list("id", flat=True))
    if not ids:
        return 0

    with connection.cursor() as cursor:
        tablas, claves = _tablas_del_demo(cursor)

        # The parents first: a table's ids are read through its
        # parent's ids, so the parent has to be read first. The LONGEST
        # path is the one that orders them - the shortest would not.
        orden = sorted(
            tablas,
            key=lambda tabla: (_camino_mas_largo(tabla, claves) or 0),
        )

        # --- the capture: the ids of the demo's rows, per table -------
        ids_por_tabla = {}
        for tabla in orden:
            directas = [
                columna
                for columna, referencia in claves.get(tabla, [])
                if referencia == "tienda_shop"
            ]
            if directas:
                cursor.execute(
                    f"SELECT id FROM {tabla} WHERE {directas[0]} = ANY(%s)", [ids]
                )
                ids_por_tabla[tabla] = [fila[0] for fila in cursor.fetchall()]
                continue

            for columna, referencia in claves.get(tabla, []):
                if referencia.startswith("auth_"):
                    continue
                if referencia not in ids_por_tabla:
                    continue
                padres = ids_por_tabla[referencia]
                if not padres:
                    continue
                cursor.execute(
                    f"SELECT id FROM {tabla} WHERE {columna} = ANY(%s)", [padres]
                )
                ids_por_tabla[tabla] = [fila[0] for fila in cursor.fetchall()]

        # --- the deletion: by the captured ids --------------------------
        for tabla in orden:
            filas = ids_por_tabla.get(tabla)
            if not filas:
                continue
            cursor.execute(f"DELETE FROM {tabla} WHERE id = ANY(%s)", [filas])

        cursor.execute("DELETE FROM tienda_shop WHERE id = ANY(%s)", [ids])
    return len(ids)
    return len(ids)
    return len(ids)
    return len(ids)
    return len(ids)
    return len(ids)
    return len(ids)
