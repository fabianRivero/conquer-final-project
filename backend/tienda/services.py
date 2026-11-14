"""The service layer — the only layer that touches the ORM.

Rows go in, plain values go through the pure rules of `domain/`, and rows
come out. Nothing else in the application is allowed to write to the
database: the views of Phase 4 call these functions and never the ORM
directly, and ADR-19 gives the ledger a single entry point for exactly
that reason.

**The three rules that shape this module.**

*Rows become plain values, never the other way round.* A rule of `domain/`
never sees an ORM object. The service converts a row into the record the
rule expects — `LedgerLine`, `CargoLine`, `CustomerState` — and converts
the result back into rows. The conversion is where the derived figures come
from, and the conversion is the only place a rule's input is built.

*The transaction is the unit of enforcement.* Every write runs inside
`transaction.atomic()`. The transactional checks of design §3.2 are the
aggregate ones — "the amount equals the sum of its lines", "the imputations
add up to the payment" — and a `CHECK` constraint cannot express an
aggregate: it sees one row and never a sum. Those checks live here, in the
transaction, and they raise `DomainValidationError` so the client gets the
422 of §9.3 instead of an `IntegrityError`.

*The per-row check has a service-level twin.* A database `CHECK` raises an
`IntegrityError`, not a `codigo_error`, so the client would see a 500. Every
per-row invariant therefore has a twin here that validates the same
condition **before** the write: `amount > 0` → `importe_no_positivo`, `kind`
outside {`cargo`, `pago`} → `tipo_desconocido`, `cantidad > 0` and
`precio_unitario ≥ 0` → `importe_no_positivo`. The `CHECK` is the backstop
under a race; the twin is what the client sees.

**What this slice does not yet do.** The four proposal routes and the
client's routes are Phases 5 and 6. The functions that serve them are not
here yet, and neither is the credential machinery of `client_auth.py`. What
is here is the foundation every later slice stands on: the conversion
between rows and plain values, the rules that can already be enforced, and
the vocabulary of refusals.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from tienda.api.exceptions import DomainValidationError
from tienda.domain import charges as reglas_cargos
from tienda.domain import evaluation as reglas_evaluacion
from tienda.domain import position as reglas_posicion
from tienda.domain.types import (
    CargoLine,
    CashLine,
    ConfirmacionRow,
    ConfirmState,
    EntryKind,
    LedgerLine,
    StockLine,
)
from tienda.models import (
    CargoLinea,
    CashMovement,
    Confirmacion,
    Customer,
    CustomerCodigo,
    DayClose,
    FiadoPropuesto,
    ImputacionPago,
    LedgerEntry,
    PagoPropuesto,
    Producto,
    PropuestaLinea,
    StockMovement,
)

# ---------------------------------------------------------------------------
# The conversions
# ---------------------------------------------------------------------------


def linea_ledger(row: LedgerEntry) -> LedgerLine:
    """A `LedgerEntry` row as the plain value the rules expect.

    This is the boundary. A rule of `domain/` never receives an ORM row,
    and this function is the only place that builds one of those inputs.
    """
    return LedgerLine(
        id=row.id,
        kind=EntryKind(row.kind),
        amount=row.amount,
        occurred_at=row.occurred_at,
    )


def linea_cargo(row: CargoLinea) -> CargoLine:
    """A `CargoLinea` row as the plain value the rules expect."""
    return CargoLine(
        id=row.id,
        cantidad=row.cantidad,
        precio_unitario=row.precio_unitario,
        total=row.total,
    )


def linea_caja(row: CashMovement) -> CashLine:
    """A `CashMovement` row as the plain value the rules expect."""
    return CashLine(
        id=row.id,
        kind=row.kind,
        amount=row.amount,
        occurred_at=row.occurred_at,
    )


def linea_stock(row: StockMovement) -> StockLine:
    """A `StockMovement` row as the plain value the rules expect."""
    return StockLine(
        id=row.id,
        kind=row.kind,
        cantidad=row.cantidad,
        occurred_at=row.occurred_at,
    )


def linea_confirmacion(row: Confirmacion) -> ConfirmacionRow:
    """A `Confirmacion` row as the plain value the rules expect."""
    return ConfirmacionRow(
        id=row.id,
        estado=ConfirmState(row.estado),
        confirmado_en=row.confirmado_en,
        origen=row.origen,
    )


def pendientes_de(customer: Customer, at=None) -> tuple[list[LedgerLine], list[LedgerLine]]:
    """The customer's charges and payments, as plain values.

    `at` is the instant the question is asked; the caller passes it, so the
    service never reads a clock on its own. `None` means "now", and it is
    the service's own clock, not the rule's.
    """
    if at is None:
        at = timezone.now()
    rows = (
        LedgerEntry.objects.filter(customer=customer)
        .order_by("occurred_at", "id")
    )
    cargos = [linea_ledger(r) for r in rows if r.kind == EntryKind.CARGO.value]
    pagos = [linea_ledger(r) for r in rows if r.kind == EntryKind.PAGO.value]
    return cargos, pagos


def pendientes_de_shop(shop, at=None) -> list[LedgerLine]:
    """Every customer's charges of a shop, as plain values.

    The ageing of the risk ladder needs the whole book at once, so the
    conversion runs over every row of the shop.
    """
    if at is None:
        at = timezone.now()
    rows = (
        LedgerEntry.objects.filter(shop=shop, kind=EntryKind.CARGO.value)
        .order_by("occurred_at", "id")
    )
    return [linea_ledger(r) for r in rows]


def estado_de(customer: Customer, at=None, override: bool = False):
    """The derived state of a customer — the suspension and its cause.

    The rule reads plain values and knows nothing about the ORM.
    """
    if at is None:
        at = timezone.now()
    cargos, pagos = pendientes_de(customer, at)
    estado = reglas_evaluacion.evaluate_customer(
        cargos + pagos,
        credit_limit=customer.credit_limit,
        at=at,
        override=override or customer.suspended_override_at is not None,
    )
    return estado


def pendiente_de(customer: Customer, at=None) -> Decimal:
    """The outstanding of a customer, derived on read."""
    if at is None:
        at = timezone.now()
    cargos, pagos = pendientes_de(customer, at)
    return reglas_posicion.outstanding(cargos + pagos, at)


# ---------------------------------------------------------------------------
# The per-row twins of the database CHECKs
# ---------------------------------------------------------------------------


def exigir_importe_positivo(amount) -> Decimal:
    """The twin of `chk_ledgerentry_amount_positive` (rule 15).

    The database refuses the row; this refuses it **first**, with the code
    the client sees. A `CHECK` raises an `IntegrityError`, and an
    `IntegrityError` that reaches DRF is a 500.
    """
    valor = Decimal(amount)
    if valor <= 0:
        raise DomainValidationError("importe_no_positivo")
    return valor


def exigir_tipo_conocido(kind) -> str:
    """The twin of `chk_ledgerentry_kind_vocabulary` (rule 16).

    The vocabulary has **two** values: `cargo` and `pago`. A third one
    would be a credit note, and credit notes died with the dispute
    machinery.
    """
    if kind not in {k.value for k in EntryKind}:
        raise DomainValidationError("tipo_desconocido")
    return kind


def exigir_cantidad_valida(cantidad, precio_unitario) -> None:
    """The twin of the per-line `CHECK`s (rules 15, 17).

    `cantidad > 0` and `precio_unitario ≥ 0`.
    """
    if Decimal(cantidad) <= 0:
        raise DomainValidationError("importe_no_positivo")
    if Decimal(precio_unitario) < 0:
        raise DomainValidationError("importe_no_positivo")


def exigir_campos_no_admitidos(payload: dict, admitidos: set[str]) -> None:
    """The twin of rule 4: the request carries a field that is not admitted.

    `occurred_at` is never client-supplied: the server stamps it. A close
    request carries no `esperado` and no `desviacion`: both are derived.
    The refusal is on the **presence** of the field, not on its value.
    """
    sobrantes = sorted(set(payload) - set(admitidos))
    if sobrantes:
        raise DomainValidationError("campo_no_admitido")


# ---------------------------------------------------------------------------
# The cash and the close
# ---------------------------------------------------------------------------


def registrar_movimiento_caja(shop, user, *, kind, amount, concept, at=None):
    """Record a movement of the drawer.

    Rule 12: the movement is server-stamped and may not be stamped in the
    future. The stamp is the server's, never the client's.
    """
    if kind not in {"entrada", "salida"}:
        raise DomainValidationError("tipo_desconocido")
    valor = exigir_importe_positivo(amount)
    momento = at or timezone.now()
    if momento > timezone.now():
        raise DomainValidationError("campo_no_admitido")
    return CashMovement.objects.create(
        shop=shop,
        user=user,
        kind=kind,
        amount=valor,
        concept=concept,
        occurred_at=momento,
    )


def cerrar_dia(shop, user, *, date, contado, at=None):
    """Close a day.

    Rules 9, 13 and 14: the `esperado` is the **derived** cash at the close
    instant — never a client-supplied figure — the day is closed once per
    shop, and the request may not carry `esperado` or `desviacion`.
    """
    if contado is None or Decimal(contado) < 0:
        raise DomainValidationError("importe_no_positivo")
    momento = at or timezone.now()

    with transaction.atomic():
        if DayClose.objects.filter(shop=shop, date=date).exists():
            raise DomainValidationError("cierre_duplicado")

        pagos = [
            linea_ledger(r)
            for r in LedgerEntry.objects.filter(
                shop=shop, kind=EntryKind.PAGO.value, occurred_at__lte=momento
            )
        ]
        movimientos = [
            linea_caja(r)
            for r in CashMovement.objects.filter(
                shop=shop, occurred_at__lte=momento
            )
        ]
        esperado = reglas_posicion.cash_at(
            shop.opening_cash, movimientos, pagos, momento
        )
        return DayClose.objects.create(
            shop=shop,
            user=user,
            date=date,
            esperado=esperado,
            contado=Decimal(contado),
            desviacion=esperado - Decimal(contado),
        )


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------


def productos_activos(shop):
    """The catalogue of a shop: the products eligible for fiado."""
    return Producto.objects.filter(shop=shop, activo=True)


def exigir_producto_de_la_tienda(shop, producto) -> Producto:
    """Rule 11: a line may not name a product of another shop."""
    if producto.shop_id != shop.id:
        raise DomainValidationError("producto_ajeno")
    return producto


# ---------------------------------------------------------------------------
# The customers and the credential
# ---------------------------------------------------------------------------


def crear_cliente(shop, user, *, alias, phone=None, credit_limit=None):
    """Register a customer.

    The owner is the author: `created_by` is stamped from the acting
    session and never read from the request body.
    """
    if credit_limit is not None and Decimal(credit_limit) < 0:
        raise DomainValidationError("importe_no_positivo")
    return Customer.objects.create(
        shop=shop,
        created_by=user,
        alias=alias,
        phone=phone,
        credit_limit=credit_limit,
    )


def cliente_de_la_tienda(shop, customer_id):
    """The customer of a shop, or `None`.

    A customer of another shop is **not found**, not refused: the answer is
    a scoped 404, so a request cannot learn that the customer exists
    elsewhere.
    """
    return Customer.objects.filter(shop=shop, id=customer_id).first()


def emitir_codigo(shop, customer, user, *, prefijo, hash_credencial, issued_at=None):
    """Issue a credential.

    Rules 10 and 11: the prefix is unique in the shop, and a customer
    holds at most one **active** credential.
    """
    if CustomerCodigo.objects.filter(shop=shop, prefix=prefijo).exists():
        raise DomainValidationError("codigo_duplicado")
    if CustomerCodigo.objects.filter(
        customer=customer, revoked_at__isnull=True
    ).exists():
        raise DomainValidationError("codigo_duplicado")
    return CustomerCodigo.objects.create(
        shop=shop,
        customer=customer,
        prefix=prefijo,
        codigo_hash=hash_credencial,
        issued_at=issued_at or timezone.now(),
        issued_by=user,
    )


def revocar_codigo(shop, codigo, user, *, at=None):
    """Revoke a credential. The revocation records an act and names its author."""
    if codigo.revoked_at is not None:
        raise DomainValidationError("codigo_duplicado")
    codigo.revoked_at = at or timezone.now()
    codigo.revoked_by = user
    codigo.save(update_fields=["revoked_at", "revoked_by"])
    return codigo


def anular_suspension(customer, user, *, at=None):
    """Lift the automatic suspension.

    The override records an **act**, never a derived value: the derived
    state stays derived, and the owner's act is what is stored.
    """
    customer.suspended_override_at = at or timezone.now()
    customer.suspended_override_by = user
    customer.save(update_fields=["suspended_override_at", "suspended_override_by"])
    return customer
