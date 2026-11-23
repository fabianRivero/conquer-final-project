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
from django.db.models import Sum
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
    PagoPropuestoEstado,
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
    Shop,
    StockMovement,
    Vinculo,
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


def pendientes_de(
    customer: Customer, at=None, tienda=None
) -> tuple[list[LedgerLine], list[LedgerLine]]:
    """The customer's charges and payments **in a shop**, as plain values.

    `at` is the instant the question is asked; the caller passes it, so the
    service never reads a clock on its own. `None` means "now", and it is
    the service's own clock, not the rule's.

    **The shop filters.** A person may owe in SEVERAL shops, and her
    debt in one of them says nothing about the others.
    """
    if at is None:
        at = timezone.now()
    filas = LedgerEntry.objects.filter(customer=customer)
    if tienda is not None:
        filas = filas.filter(shop=tienda)
    rows = filas.order_by("occurred_at", "id")
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


def estado_de(customer: Customer, at=None, override: bool = False, tienda=None):
    """The derived state of a customer **in a shop** — the suspension and
    its cause.

    The rule reads plain values and knows nothing about the ORM.

    **The limit is the LINK's**, so the state is per shop: a person may
    be over her limit in one shop and under it in another, and the
    ageing is per shop too.
    """
    if at is None:
        at = timezone.now()
    cargos, pagos = pendientes_de(customer, at, tienda=tienda)
    limite = None
    if tienda is not None:
        vinculo = Vinculo.objects.filter(
            tienda=tienda, cliente=customer, estado="aceptado"
        ).first()
        if vinculo is not None:
            limite = vinculo.credit_limit
    estado = reglas_evaluacion.evaluate_customer(
        cargos + pagos,
        credit_limit=limite,
        at=at,
        override=override or customer.suspended_override_at is not None,
    )
    return estado


def pendiente_de(customer: Customer, at=None, tienda=None) -> Decimal:
    """The outstanding of a customer **in a shop**, derived on read."""
    if at is None:
        at = timezone.now()
    cargos, pagos = pendientes_de(customer, at, tienda=tienda)
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
    """Register a customer **of a shop**.

    The person is created - she belongs to **no** shop - and the LINK is
    created with her: **accepted**, because the owner is registering her
    as a customer he trusts. The limit travels with the link, and a NULL
    limit is "sin límite".

    The owner is the author: `created_by` is stamped from the acting
    session and never read from the request body.
    """
    if credit_limit is not None and Decimal(credit_limit) < 0:
        raise DomainValidationError("importe_no_positivo")

    cliente, _ = Customer.objects.get_or_create(
        alias=alias,
        defaults={"created_by": user, "phone": phone},
    )
    Vinculo.objects.create(
        tienda=shop,
        cliente=cliente,
        estado="aceptado",
        credit_limit=credit_limit,
        pedido_at=timezone.now(),
        pedido_por=user,
        aceptado_at=timezone.now(),
    )
    return cliente


def cliente_de_la_tienda(shop, customer_id):
    """The customer of a shop, or `None`.

    A customer of another shop is **not found**, not refused: the answer is
    a scoped 404, so a request cannot learn that the customer exists
    elsewhere.

    **And a customer who is not a TRUSTED client of the shop is not
    found either**: the link is what says she belongs to it.
    """
    return (
        Vinculo.objects.filter(
            tienda=shop, cliente_id=customer_id, estado="aceptado"
        )
        .values_list("cliente_id", flat=True)
        .first()
        and Customer.objects.filter(id=customer_id).first()
    )


def vinculo_de(shop, customer) -> "Vinculo | None":
    """The link of a customer to a shop, or `None`.

    **The link is what says she belongs to the shop** - the person
    belongs to no shop, and she may be a trusted client of SEVERAL.
    """
    return Vinculo.objects.filter(tienda=shop, cliente=customer).first()


def reclamar_cliente(user, alias):
    """The person claims the customer row the shop created for her.

    **The shop registers a person before she has an account.** She is a
    customer of the shop and of nobody else, and the row carries the
    alias the shop calls her by. Then she registers herself - she chose
    her username, and the username is not the alias - and the row is
    still there, waiting for her.

    This is the meeting: **the account and the row are the same human**,
    and the `Customer.user` field is where the model says so.

    **The alias is what the shop typed, and she confirms it.** The row is
    not claimed because it LOOKS like hers: it is claimed because she
    named the alias the shop gave her, and the row is a row of a shop's
    list of people that nobody has claimed yet.

    **A row that is already claimed is not taken.** The uniqueness is a
    constraint, and a person is ONE row.
    """
    alias = (alias or "").strip()
    if not alias:
        raise DomainValidationError("alias_requerido")

    cliente = Customer.objects.filter(alias=alias, user__isnull=True).first()
    if cliente is None:
        # Either there is no such row, or it is already somebody else's.
        # **The refusal does not say which**: "that row is taken" tells
        # the person that a row with that alias exists, and the alias
        # is the shop's name for her - it is not a secret, but the
        # answer is the same either way so that nothing can be learned
        # from the refusal.
        raise DomainValidationError("alias_no_reclamable")

    cliente.user = user
    cliente.save(update_fields=["user"])
    return cliente


def vinculos_del_cliente(cliente) -> list:
    """The links of a client, as **she** sees them.

    **A pending link shows the shop's name and nothing else.** If she
    could see the debt and the ageing first, the consent would be a
    formality - she would already have seen everything the acceptance
    reveals. The link she is asked about says which shop is asking, and
    no more.
    """
    filas = []
    for vinculo in Vinculo.objects.filter(cliente=cliente).select_related("tienda"):
        fila = {
            "id": vinculo.id,
            "tienda": vinculo.tienda.name,
            "estado": vinculo.estado,
        }
        if vinculo.estado == "aceptado":
            # The acceptance is what opens the owner's figures to her.
            fila["credit_limit"] = vinculo.credit_limit
            fila["pendiente"] = pendiente_de(cliente, tienda=vinculo.tienda)
        filas.append(fila)
    return filas


def pedir_vinculo(user, tienda, cliente, *, credit_limit=None):
    """The owner asks a person to be a trusted client of the shop.

    **The question is the owner's; the answer is the client's.** The
    link is created `pendiente`, and only she may accept or refuse it.

    **The re-integration goes through `pendiente` again**: the owner may
    ask, but the consent does not come back by itself.
    """
    if credit_limit is not None and Decimal(credit_limit) < 0:
        raise DomainValidationError("importe_no_positivo")

    vinculo, _ = Vinculo.objects.get_or_create(
        tienda=tienda,
        cliente=cliente,
        defaults={
            "estado": "pendiente",
            "credit_limit": credit_limit,
            "pedido_at": timezone.now(),
            "pedido_por": user,
        },
    )
    if vinculo.estado != "pendiente":
        # The owner asks again: the link goes back to the question, and
        # the client's answer is asked for once more.
        vinculo.estado = "pendiente"
        vinculo.pedido_at = timezone.now()
        vinculo.pedido_por = user
        vinculo.aceptado_at = None
        vinculo.rechazado_at = None
        vinculo.eliminado_at = None
        vinculo.eliminado_por = None
        if credit_limit is not None:
            vinculo.credit_limit = credit_limit
        vinculo.save()
    return vinculo



def _tienda_de(tienda):
    """The shop of an id, or the shop itself.

    The client's route receives the id in the body; the owner's route
    has it in the session. The service does not care where it came from.
    """
    if tienda is None:
        return None
    if hasattr(tienda, "id"):
        return tienda
    return Shop.objects.filter(id=tienda).first()


def aceptar_vinculo(cliente, vinculo_id):
    """The client accepts the link of a shop.

    **Only she may do it**: the shop does not have her credentials, and
    it must not decide for her.
    """
    vinculo = Vinculo.objects.filter(
        id=vinculo_id, cliente=cliente, estado="pendiente"
    ).first()
    if vinculo is None:
        raise DomainValidationError("vinculo_no_pendiente")

    vinculo.estado = "aceptado"
    vinculo.aceptado_at = timezone.now()
    vinculo.rechazado_at = None
    vinculo.save(update_fields=["estado", "aceptado_at", "rechazado_at"])
    return vinculo


def rechazar_vinculo(cliente, vinculo_id):
    """The client refuses the link of a shop.

    **A refusal is not a removal**: the shop may ask again, and she may
    answer differently the next time.
    """
    vinculo = Vinculo.objects.filter(
        id=vinculo_id, cliente=cliente, estado="pendiente"
    ).first()
    if vinculo is None:
        raise DomainValidationError("vinculo_no_pendiente")

    vinculo.estado = "rechazado"
    vinculo.rechazado_at = timezone.now()
    vinculo.aceptado_at = None
    vinculo.save(update_fields=["estado", "rechazado_at", "aceptado_at"])
    return vinculo


def eliminar_vinculo(user, tienda, cliente):
    """The owner takes the client off the trusted list - **and does not ask**.

    **The removal is the owner's alone**: the client does not consent to
    being removed, and the shop does not need her to. Her debts and her
    history stay - the book is append-only - but the confidence is gone,
    and no new fiado can be made.
    """
    vinculo = Vinculo.objects.filter(
        tienda=_tienda_de(tienda), cliente=cliente
    ).first()
    if vinculo is None:
        raise Http404

    vinculo.estado = "eliminado"
    vinculo.eliminado_at = timezone.now()
    vinculo.eliminado_por = user
    vinculo.save(update_fields=["estado", "eliminado_at", "eliminado_por"])
    return vinculo


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


def _origen_de(user, shop_id):
    """What KIND of act a confirmation is, inferred from the acting session.

    Rule 7b: the origin is **inferred by the server**, never read from the
    request body. The `dependiente` recording the confirmation is
    `dependiente`; the owner recording it is `tienda`.

    The origin says **what kind of act** it was, not who did it - the name
    of the actor is in `Confirmacion.confirmado_por`, and it is always
    there. The two are different questions: a `dependiente` recording a
    confirmation is a **counter act** by the shop's staff, and the row
    says so twice, once as a kind and once as a name.
    """
    from tienda.api.permissions import es_dependiente

    return "dependiente" if es_dependiente(user, shop_id) else "tienda"


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


def _propuesta_bloqueada(shop_id, propuesta_id: int, *, user=None) -> FiadoPropuesto:
    """The proposal of a shop, with its row locked.

    The lock is what makes the check-then-write atomic: a second
    confirmation of the same proposal waits here and then reads the state
    the first one wrote.

    A proposal of another shop is **NOT FOUND**, not refused: the answer is
    a scoped 404, so a request cannot learn that the proposal exists
    elsewhere.

    **The ownership filter.** With the N5 gate open, a `dependiente`
    confirms and cancels only the proposals **it prepared**. The filter is
    on the queryset - the shop scope and the ownership scope are filters on
    the same read - and it applies to every role: the owner confirms the
    proposals it prepared, the `dependiente` confirms its own, and nobody
    confirms somebody else's. The refusal is a **404**, not a 403: a 403
    would confirm that the proposal exists.
    """
    from tienda.api.permissions import es_dependiente

    filtros = {"shop_id": shop_id, "id": propuesta_id}
    if user is not None and es_dependiente(user, shop_id):
        filtros["user_id"] = user.id

    propuesta = (
        FiadoPropuesto.objects.select_for_update().filter(**filtros).first()
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
        propuesta = _propuesta_bloqueada(shop_id, propuesta_id, user=user)

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
        estado_cliente = estado_de(propuesta.customer, at=momento, tienda=shop_id)
        if estado_cliente.suspendido:
            motivo = estado_cliente.motivo
            raise DomainValidationError(
                motivo.value if motivo is not None else "limite_superado"
            )

        # Rule 7b: the origin, inferred from the acting session, and the
        # actor, who is always named.
        origen = _origen_de(user, shop_id)

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
            confirmado_por=user,
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
        propuesta = _propuesta_bloqueada(shop_id, propuesta_id, user=user)

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


# ---------------------------------------------------------------------------
# The client's own reads, and the proposed payment - tasks 6.4 to 6.8
# ---------------------------------------------------------------------------


def cargos_de_la_tienda(customer: Customer, at=None, tienda=None) -> list:
    """The customer's CONFIRMED charges, as ORM rows.

    **Confirmed only.** A charge without its `Confirmacion` does not
    exist - the client confirms in the shop, and only then does the
    charge become debt (ADR-19). The confirmation is therefore a filter
    on the read, not a decoration on the payload.

    The rows come back in the order the FIFO retires them: oldest
    first, and by id within the same instant.
    """
    if at is None:
        at = timezone.now()
    return list(
        LedgerEntry.objects.filter(
            shop=tienda,
            customer=customer,
            kind=EntryKind.CARGO.value,
            occurred_at__lte=at,
        )
        .filter(confirmaciones__estado=ConfirmState.CONFIRMADO.value)
        .order_by("occurred_at", "id")
        .distinct()
    )


def cargo_de_la_tienda(customer: Customer, cargo_id: int):
    """One of the customer's confirmed charges, or `None`.

    A charge of another customer is **not found**, not refused: the
    answer says nothing about whether it exists. The route turns that
    into `cargo_ajeno`, because the client asked for a charge by id and
    the id it named is not one of its own.
    """
    return (
        LedgerEntry.objects.filter(
            customer=customer,
            kind=EntryKind.CARGO.value,
            id=cargo_id,
        )
        .filter(confirmaciones__estado=ConfirmState.CONFIRMADO.value)
        .first()
    )


def pagado_de(cargo) -> Decimal:
    """How much of a charge the client has already paid.

    **Derived on read**, never stored: `pagado` is the sum of the
    `ImputacionPago` rows against the charge, and `saldo` is the
    amount minus it. A mutable `pagado` column on the charge would
    break the append-only guarantee of the book and would be a stored
    derived value, which design 3.1 forbids and landmine 12 polices
    (ADR-27).
    """
    total = (
        ImputacionPago.objects.filter(cargo=cargo).aggregate(
            suma=Sum("importe")
        )["suma"]
        or Decimal("0")
    )
    return Decimal(total)


def saldo_de(cargo) -> Decimal:
    """What is still owed on a charge: its amount minus its `pagado`."""
    return Decimal(cargo.amount) - pagado_de(cargo)


def cliente_para_el_dependiente(
    customer: Customer, at=None, tienda=None, vinculo=None
) -> dict:
    """One customer, as the `dependiente` sees it at the counter.

    The `dependiente` records the payments, and recording needs to see
    the debt. What it sees is the **alias**, the **outstanding** and the
    **confirmed charges** with their itemisation.

    **What it does not see** is the owner's policy: the `credit_limit`,
    the `antiguedad_max_dias`, the `suspended_reason`, the `codigo` and
    the `prefix`. The function does not build those keys at all, so they
    cannot reach the response - the boundary is the absence of the field,
    not a filter applied afterwards.

    The charges are the **confirmed** ones: a charge without its
    `Confirmacion` does not exist, and a pending proposal is not a debt
    yet (ADR-19).

    **The debt is of ONE shop.** The book is the shop's, and the limit
    that holds it is the LINK's - so both the charges and the limit say
    which shop they are about.
    """
    if at is None:
        at = timezone.now()

    if tienda is None and vinculo is not None:
        tienda = vinculo.tienda

    cargos = cargos_de_la_tienda(customer, at, tienda=tienda)

    filas = []
    pendiente = Decimal("0")
    for cargo in cargos:
        pagado = pagado_de(cargo)
        saldo = saldo_de(cargo)
        pendiente += saldo
        filas.append(
            {
                "id": cargo.id,
                "fecha": cargo.occurred_at,
                "amount": cargo.amount,
                "confirmado_en": getattr(
                    cargo.confirmaciones.first(), "confirmado_en", None
                ),
                "pagado": pagado,
                "saldo": saldo,
                "lineas": [
                    {
                        "producto": linea.producto.nombre,
                        "cantidad": linea.cantidad,
                        "precio_unitario": linea.precio_unitario,
                        "total": linea.total,
                    }
                    for linea in cargo.lineas.order_by("id")
                ],
            }
        )

    return {
        "id": customer.id,
        "alias": customer.alias,
        "pendiente": pendiente,
        "cargos": filas,
    }


def proponer_pago(
    customer: Customer, *, importe, referencia="", at=None, shop_id=None
):
    """The client proposes a payment. Nothing is written to the book.

    The proposal creates a `PagoPropuesto(pendiente)` and **no ledger
    row**: the `pago` itself is a separate `LedgerEntry` that the OWNER
    appends when he validates it. The book stays append-only even though
    the request that preceded it is not (CC-07, PA-09).

    Rule 17: the amount is strictly positive.

    **The proposal names NO charge.** The client does not choose which
    debt it pays: it proposes an amount and the FIFO decides which
    charges it retires (ADR-27). There is no `cargo_id` on the entity,
    and the route refuses a body that carries one.
    """
    valor = Decimal(importe)
    if valor <= 0:
        raise DomainValidationError("importe_no_positivo")

    if shop_id is None:
        vinculo = Vinculo.objects.filter(
            cliente=customer, estado="aceptado"
        ).first()
        shop_id = vinculo.tienda_id if vinculo is not None else None

    return PagoPropuesto.objects.create(
        shop_id=shop_id,
        customer=customer,
        importe=valor,
        referencia=referencia or "",
        estado=PagoPropuestoEstado.PENDIENTE.value,
        created_at=at or timezone.now(),
    )


def _pago_propuesto_bloqueado(shop_id, pago_id: int) -> PagoPropuesto:
    """The proposed payment of a shop, with its row locked.

    The move is one-way (rule 18), so two validations of the same
    proposal must not both pass the state check: the lock is what makes
    the check-then-write atomic.
    """
    propuesta = (
        PagoPropuesto.objects.select_for_update()
        .filter(shop_id=shop_id, id=pago_id)
        .first()
    )
    if propuesta is None:
        raise Http404
    return propuesta


def validar_pago(shop_id, user, *, pago_id: int, at=None):
    """The owner validates a proposed payment. **The `pago` is written here.**

    The write is one transaction, and it appends three things together:
    the `LedgerEntry(pago)`, its `ImputacionPago` rows - one per charge
    the payment retires, FIFO by charge - and the `PagoPropuesto`'s
    move to `validado` with its `resolved_at` and `resolved_by_id`.

    **The amount is EXACTLY the proposal's `importe`** - never
    recomputed, never rounded. The proposal is what the client asked
    for; the owner's act is to record it, not to change it.

    Rule 19: a `pago` never exceeds the debt it retires. The bound is
    the customer's TOTAL outstanding, not one charge's. The excess
    leaves the counter as change and never enters the book, so no
    customer credit can exist (ADR-26).

    Rule 18: a proposal is resolved once. A second validation is
    refused with `pago_ya_resuelto` and appends no second `pago`.
    """
    momento = at or timezone.now()

    with transaction.atomic():
        propuesta = _pago_propuesto_bloqueado(shop_id, pago_id)

        # Rule 18: the move is one-way.
        if propuesta.estado != PagoPropuestoEstado.PENDIENTE.value:
            raise DomainValidationError("pago_ya_resuelto")

        # Rule 19: the bound is the outstanding of **THIS shop**.
        #
        # The person may owe in SEVERAL shops, and a payment at this
        # counter enters THIS book only. The debt of the other shop is
        # not here, and this payment will not go there either: the bound
        # is the debt the payment actually retires.
        #
        # Before the 10.3 the customer belonged to one shop, so "the
        # customer's total outstanding" and "the shop's outstanding"
        # were the same number. They stopped being the same number the
        # day the person became a person.
        pendiente = pendiente_de(propuesta.customer, momento, tienda=shop_id)
        if Decimal(propuesta.importe) > pendiente:
            raise DomainValidationError("pago_excede_deuda")

        pago = LedgerEntry.objects.create(
            shop_id=shop_id,
            customer=propuesta.customer,
            user=user,
            kind=EntryKind.PAGO.value,
            amount=propuesta.importe,
            occurred_at=momento,
        )

        # The repartition, recorded per charge (ADR-27).
        #
        # **The charges are THIS shop's.** The FIFO sorts by date, and
        # over every shop the person's oldest charge came first - so the
        # allocation could settle ANOTHER shop's charge with THIS
        # shop's money, and the `ImputacionPago` row said so forever, in
        # a book that is append-only.
        from tienda.domain import allocation as reglas_asignacion

        cargos, _ = pendientes_de(propuesta.customer, momento, tienda=shop_id)
        asignacion = reglas_asignacion.allocate_payments(
            cargos, [linea_ledger(pago)]
        )
        for imputacion in reglas_asignacion.imputations_of(asignacion, pago.id):
            ImputacionPago.objects.create(
                pago=pago,
                cargo_id=imputacion.cargo_id,
                importe=imputacion.importe,
            )

        propuesta.estado = PagoPropuestoEstado.VALIDADO.value
        propuesta.resolved_at = momento
        propuesta.resolved_by = user
        propuesta.save(update_fields=["estado", "resolved_at", "resolved_by"])
    return pago, propuesta


def rechazar_pago(shop_id, user, *, pago_id: int, at=None):
    """The owner rejects a proposed payment. **No `pago` is written.**

    The proposal moves to `rechazado` with its `resolved_at` and its
    `resolved_by_id`, and the book is untouched: the client asked and
    the owner said no.
    """
    momento = at or timezone.now()

    with transaction.atomic():
        propuesta = _pago_propuesto_bloqueado(shop_id, pago_id)

        # Rule 18: the move is one-way.
        if propuesta.estado != PagoPropuestoEstado.PENDIENTE.value:
            raise DomainValidationError("pago_ya_resuelto")

        propuesta.estado = PagoPropuestoEstado.RECHAZADO.value
        propuesta.resolved_at = momento
        propuesta.resolved_by = user
        propuesta.save(update_fields=["estado", "resolved_at", "resolved_by"])
    return propuesta
