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
from django.http import Http404
from django.utils import timezone

from tienda.api.exceptions import DomainValidationError
from tienda.domain import charges as reglas_cargos
from tienda.domain import confirmation as reglas_confirmacion
from tienda.domain import evaluation as reglas_evaluacion
from tienda.domain import position as reglas_posicion
from tienda.domain.types import (
    CargoLine,
    CashLine,
    ConfirmacionRow,
    ConfirmState,
    EntryKind,
    LedgerLine,
    PropuestaEstado,
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


# ---------------------------------------------------------------------------
# The proposal - tasks 5.8, CC-01, IC-03
# ---------------------------------------------------------------------------


def _precio_de_linea(producto: Producto, precio_unitario) -> Decimal:
    """The unit price of a proposal line.

    The price is a **snapshot** (IC-08): the catalogue holds the current
    price, and the line freezes the price offered at the moment the
    proposal was prepared. A later catalogue change never rewrites a
    stored line.

    The rule is `domain.charges.precio_unitario_de`: the override wins when
    it is present, and the catalogue price is the price otherwise.
    """
    return reglas_cargos.precio_unitario_de(producto.precio, precio_unitario)


def _facilitador_de(user):
    """The facilitator of a proposal, inferred from the acting session.

    Rule 7b: the origin is **inferred by the server**, never read from the
    request body. The `dependiente` presenting the proposal at the counter
    is `facilitado` and names itself; the owner is `tienda` and names
    nobody.
    """
    from tienda.api.permissions import es_dependiente

    return user if es_dependiente(user) else None


def preparar_propuesta(
    shop_id,
    user,
    *,
    customer: Customer,
    lineas: list[dict],
    total=None,
    at=None,
):
    """Prepare a proposal - a fiado the client has not confirmed yet.

    **Nothing is written to the book.** The proposal and its itemisation
    are stored, and the outstanding does not move: a proposal is a request,
    and the charge exists only at the confirmation (ADR-19).

    Rule 3 - the itemisation is mandatory: the declared total equals the
    sum of the lines, and a proposal with no lines is refused with the same
    code. A figure the client cannot see broken down is not a figure the
    client confirmed.

    Rule 11 - a line may not name a product of another shop.

    The `facilitado_por` of the proposal is written **at INSERT**, by the
    same server-side inference as rule 7b. It is never written afterwards.
    """
    if not lineas:
        raise DomainValidationError("lineas_descuadradas")

    momento = at or timezone.now()

    filas = []
    for linea in lineas:
        producto = Producto.objects.filter(id=linea.get("producto_id")).first()
        if producto is None or producto.shop_id != shop_id:
            raise DomainValidationError("producto_ajeno")
        cantidad = Decimal(linea["cantidad"])
        precio = _precio_de_linea(producto, linea.get("precio_unitario"))
        if cantidad <= 0:
            raise DomainValidationError("importe_no_positivo")
        if precio < 0:
            raise DomainValidationError("importe_no_positivo")
        filas.append(
            {
                "producto": producto,
                "cantidad": cantidad,
                "precio_unitario": precio,
                "total": reglas_cargos.total_de_linea(cantidad, precio),
            }
        )

    suma = sum((fila["total"] for fila in filas), Decimal("0"))
    if total is not None and Decimal(total) != suma:
        raise DomainValidationError("lineas_descuadradas")

    with transaction.atomic():
        propuesta = FiadoPropuesto.objects.create(
            shop_id=shop_id,
            customer=customer,
            user=user,
            estado=PropuestaEstado.PENDIENTE.value,
            total=suma,
            created_at=momento,
            facilitado_por=_facilitador_de(user),
        )
        PropuestaLinea.objects.bulk_create(
            [
                PropuestaLinea(
                    propuesta=propuesta,
                    producto=fila["producto"],
                    cantidad=fila["cantidad"],
                    precio_unitario=fila["precio_unitario"],
                    total=fila["total"],
                )
                for fila in filas
            ]
        )
    return propuesta


def _propuesta_bloqueada(shop_id, propuesta_id: int) -> FiadoPropuesto:
    """The proposal of a shop, with its row locked.

    The lock is what makes the check-then-write atomic: a second
    confirmation of the same proposal waits here and then reads the state
    the first one wrote.

    A proposal of another shop is **NOT FOUND**, not refused: the answer is
    a scoped 404, so a request cannot learn that the proposal exists
    elsewhere.
    """
    propuesta = (
        FiadoPropuesto.objects.select_for_update()
        .filter(shop_id=shop_id, id=propuesta_id)
        .first()
    )
    if propuesta is None:
        raise Http404
    return propuesta


def confirmar_propuesta(shop_id, user, *, propuesta_id: int, at=None):
    """Confirm a proposal - **the only path that creates a charge**.

    The write is one transaction and it writes four things together: the
    `LedgerEntry(cargo)`, the `CargoLinea[]` copied from the proposal's own
    lines, the `Confirmacion(confirmado)` and the `FiadoPropuesto.confirmed_at`.
    If any of them fails, none of them survives.

    Rule 7 - the transition is one-way: a proposal that is not `pendiente`
    is refused with `propuesta_ya_confirmada` or `propuesta_ya_cancelada`.

    Rule 8 - a proposal confirmed while the customer is suspended writes
    **no** charge. The suspension is derived, never stored, and it is read
    INSIDE the transaction: a customer suspended a moment ago is suspended
    now.

    Rule 7b - the origin is inferred by the server from the acting session.
    """
    momento = at or timezone.now()

    with transaction.atomic():
        propuesta = _propuesta_bloqueada(shop_id, propuesta_id)

        # Rule 7: the transition, decided by the stored state.
        destino = PropuestaEstado.CONFIRMADO.value
        error = reglas_confirmacion.propuesta_transicion_permitida(
            propuesta.estado, destino
        )
        if error is not None:
            raise DomainValidationError(error)

        # Rule 3: the declared total equals the sum of the proposal's own
        # lines. The lines are the ones that will be copied, so this is the
        # last point where a mismatch can be refused.
        lineas = list(propuesta.lineas.order_by("id"))
        if not reglas_cargos.propuesta_amount_matches(
            [
                CargoLine(
                    id=linea.id,
                    cantidad=linea.cantidad,
                    precio_unitario=linea.precio_unitario,
                    total=linea.total,
                )
                for linea in lineas
            ],
            propuesta.total,
        ):
            raise DomainValidationError("lineas_descuadradas")

        # Rule 8: the derived suspension, read inside the transaction.
        estado_cliente = estado_de(propuesta.customer, at=momento)
        if estado_cliente.suspendido:
            motivo = estado_cliente.motivo
            raise DomainValidationError(
                motivo.value if motivo is not None else "limite_superado"
            )

        # Rule 7b: the origin, inferred from the acting session.
        facilitado = _facilitador_de(user)
        origen = "facilitado" if facilitado is not None else "tienda"

        cargo = LedgerEntry.objects.create(
            shop_id=shop_id,
            customer=propuesta.customer,
            user=user,
            kind=EntryKind.CARGO.value,
            amount=propuesta.total,
            occurred_at=momento,
        )
        CargoLinea.objects.bulk_create(
            [
                CargoLinea(
                    cargo=cargo,
                    producto=linea.producto,
                    cantidad=linea.cantidad,
                    precio_unitario=linea.precio_unitario,
                    total=linea.total,
                )
                for linea in lineas
            ]
        )
        Confirmacion.objects.create(
            cargo=cargo,
            estado=ConfirmState.CONFIRMADO.value,
            confirmado_en=momento,
            origen=origen,
            facilitado_por=facilitado,
        )
        propuesta.estado = destino
        propuesta.confirmed_at = momento
        propuesta.save(update_fields=["estado", "confirmed_at"])
    return cargo, propuesta


def cancelar_propuesta(shop_id, user, *, propuesta_id: int, at=None):
    """Cancel a proposal - the client declined.

    **Nothing is written but the instant.** No charge, no lines, no
    confirmation: the outstanding never moved, because it never moved in
    the first place (CC-04, design 13.2).

    Rule 7: the transition is one-way, so a proposal that is not
    `pendiente` is refused - `propuesta_ya_confirmada` when it was
    confirmed, `propuesta_ya_cancelada` when it was already cancelled.
    """
    momento = at or timezone.now()

    with transaction.atomic():
        propuesta = _propuesta_bloqueada(shop_id, propuesta_id)

        destino = PropuestaEstado.CANCELADO.value
        error = reglas_confirmacion.propuesta_transicion_permitida(
            propuesta.estado, destino
        )
        if error is not None:
            raise DomainValidationError(error)

        propuesta.estado = destino
        propuesta.canceled_at = momento
        propuesta.save(update_fields=["estado", "canceled_at"])
    return propuesta
