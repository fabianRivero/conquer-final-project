"""The plain records and the closed vocabularies of the domain layer.

This module is the type surface of design §10. Everything here is a **plain
value**: a `dataclass` or a `str` enum, never a Django model, never a lazy
translation, never a query object. The service layer of Phase 4 is the only
place that converts ORM rows into these records; the rules never see a row.

Two rules govern the shapes declared here.

**No implicit clock.** No record carries "now". Every rule that needs the
current instant takes it as the `at` argument, so a rule is a total function
of its inputs and a test can pin any instant it likes.

**No derived value is stored.** `CustomerState`, `ChargeState` and
`Allocation` are *results*, computed on read from the ledger rows. Nothing in
this module mirrors a database column that design §3 forbids — there is no
`saldo`, no `status`, no `stock`, no stored confirmation state and no stored
customer credit.

The vocabularies are `str` enums so that a member compares equal to its plain
string and serialises to it unchanged, which is what the JSON contract of
Phase 4 needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class EntryKind(str, Enum):
    """The kind of a `LedgerEntry` — the vocabulary of `LEDGER_ENTRY_KINDS`.

    `cargo` adds debt and `pago` retires it. **There are two values.** The
    third one the v1 model carried — `nota_credito` — is gone with the dispute
    machinery: the client confirms the charge before it exists, so there is
    nothing to reconcile afterwards.

    The values are the exact strings the database `CHECK` accepts.
    """

    CARGO = "cargo"
    PAGO = "pago"


class Bucket(str, Enum):
    """The four ageing ribbons of PA-03.

    A charge is bucketed by **its own** age, and the four buckets are a
    partition of the same unpaid charges — so their totals sum exactly to the
    outstanding, never a separate figure.
    """

    VIGENTE = "vigente"
    ENVEJECIDO = "envejecido"
    VIEJO = "viejo"
    CRONICO = "cronico"


class SuspensionReason(str, Enum):
    """Why a customer reads `suspendido` — the vocabulary of PA-06.

    Both causes are **derived on read**; neither is ever a stored column. A
    customer with `credit_limit = None` («sin límite») can never fire
    `LIMITE_SUPERADO`.
    """

    LIMITE_SUPERADO = "limite_superado"
    ANTIGUEDAD_SUPERADA = "antiguedad_superada"


class ConfirmState(str, Enum):
    """The effective state of a `cargo`, derived from its `Confirmacion` rows.

    `SIN_CONFIRMAR` is the state of a charge that carries no row at all. The
    state is a read-time projection (IC-04), never a stored value and never the
    guard for a write.

    **There are two values.** The v1 model carried a third — `en_disputa` —
    and with it the whole dispute machinery. A charge either carries its
    confirmation or it does not exist (ADR-18).
    """

    SIN_CONFIRMAR = "sin_confirmar"
    CONFIRMADO = "confirmado"


class PropuestaEstado(str, Enum):
    """The state of a `FiadoPropuesto` — the vocabulary of §6.

    A proposal moves from `pendiente` to exactly one of `confirmado` or
    `cancelado`, **never back**. The move is one-way, and the guard for it is
    the **stored** proposal state, not a projection of the ledger.
    """

    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    CANCELADO = "cancelado"


class PagoPropuestoEstado(str, Enum):
    """The state of a `PagoPropuesto` — the vocabulary of §13.3.

    A proposed payment moves from `pendiente` to exactly one of `validado` or
    `rechazado`, **never back**. The owner's decision is an act, recorded on
    the row.
    """

    PENDIENTE = "pendiente"
    VALIDADO = "validado"
    RECHAZADO = "rechazado"


class StockQualifier(str, Enum):
    """The ceiling qualifier carried by `existencias_registradas` (CP-07).

    `techo_no_conteo` marks the figure as a **ceiling**, not a count: the
    recorded movements are what the shop logged, never a verified inventory.
    No rule, price, limit or suspension depends on it.
    """

    TECHO_NO_CONTEO = "techo_no_conteo"


class MovementKind(str, Enum):
    """The kind of a `CashMovement` or a `StockMovement`.

    `entrada` adds to the drawer or the shelf, `salida` takes from it. The
    values are the exact strings the database `CHECK` accepts.
    """

    ENTRADA = "entrada"
    SALIDA = "salida"


@dataclass(frozen=True)
class LedgerLine:
    """One row of the credit book, as a plain value.

    Mirrors `LedgerEntry` without touching the ORM: `kind`, `amount` and
    `occurred_at`. `id` is the row's own identifier, which is the
    **tie-breaker** of the FIFO order of PA-02.

    There is **no `cargo` field** any more. The v1 record carried the
    optional `cargo` a credit note reconciled; with the dispute machinery
    gone there is nothing to reconcile, and a payment's repartition is
    recorded in `Imputacion` instead (ADR-27).
    """

    id: int
    kind: EntryKind
    amount: Decimal
    occurred_at: datetime


@dataclass(frozen=True)
class CargoLine:
    """One itemised line of a `cargo`, as a plain value.

    Mirrors `CargoLinea`: `cantidad`, `precio_unitario` and `total`. The
    `total` is the rounded line total of IC-06 — the same rounding the
    database `CHECK` mirrors.
    """

    id: int
    cantidad: Decimal
    precio_unitario: Decimal
    total: Decimal


@dataclass(frozen=True)
class PropuestaLine:
    """One itemised line of a `FiadoPropuesto`, as a plain value.

    Mirrors `PropuestaLinea`, and carries the same arithmetic as `CargoLine`:
    the `desglose` the client confirms is a real figure, not an annotation.
    """

    id: int
    cantidad: Decimal
    precio_unitario: Decimal
    total: Decimal


@dataclass(frozen=True)
class CashLine:
    """One movement of the drawer, as a plain value.

    Mirrors `CashMovement`: `kind`, `amount` and `occurred_at`. A `pago` is
    **never** a `CashMovement` — it is a `LedgerLine` of kind `pago`, and
    `cash_at` counts the two separately.
    """

    id: int
    kind: MovementKind
    amount: Decimal
    occurred_at: datetime


@dataclass(frozen=True)
class StockLine:
    """One movement of the shelf, as a plain value.

    Mirrors `StockMovement`: `kind`, `cantidad` and `occurred_at`.
    """

    id: int
    kind: MovementKind
    cantidad: Decimal
    occurred_at: datetime


@dataclass(frozen=True)
class Allocation:
    """The result of retiring debt with the money that came back (PA-02).

    `asignaciones` holds one entry per (payment, charge) pair: how much of
    which payment retired which charge. The `saldo` of each charge is what is
    still owed on it.

    `residual` is the surplus that matched nothing. **It is always zero.**
    Rule 19 refuses a `pago` larger than the debt it retires — the shop
    returns the excess as change and it never enters the book — so a surplus
    is not a legal state. The field is kept so a caller that reads it has one
    shape to read, not because a surplus can happen (ADR-26).
    """

    asignaciones: tuple[tuple[int, int, Decimal], ...] = ()
    residual: Decimal = Decimal("0")
    saldos: tuple[tuple[int, Decimal], ...] = ()


@dataclass(frozen=True)
class Imputacion:
    """One (payment, charge) pair — how much of a charge a payment settled.

    Mirrors the `ImputacionPago` row: `pago_id`, `cargo_id` and `importe`.

    **The grain is the charge.** A charge of 15,00 € made of three
    `CargoLinea` rows is one debt of 15,00 €, and a payment that settles
    5,00 € of it produces **one** imputation against the charge, not three
    against the lines (ADR-27).
    """

    pago_id: int
    cargo_id: int
    importe: Decimal


@dataclass(frozen=True)
class CustomerState:
    """The derived state of a customer — PA-05 and PA-06, computed on read.

    `suspendido` is the derived flag; `motivo` carries the cause when the
    customer is suspended and is `None` otherwise. `antiguedad_max_dias` is
    the age of the oldest unpaid charge — 0 when nothing is owed.

    Nothing here is stored: `Customer` has no `status` and no
    `suspended_reason` column (D1).
    """

    alias: str
    total: Decimal
    antiguedad_max_dias: int
    suspendido: bool
    motivo: Optional[SuspensionReason] = None
    credit_limit: Optional[Decimal] = None


@dataclass(frozen=True)
class ConfirmacionRow:
    """One `Confirmacion` row, as a plain value.

    Mirrors the table: `estado`, `confirmado_en` and the `id` that orders the
    history. `origen` records who appended the row.

    There is **no `importe_reclamado`** — the field existed only for the
    dispute machinery, and it is gone with it.
    """

    id: int
    estado: ConfirmState
    confirmado_en: Optional[datetime] = None
    origen: str = "tienda"


@dataclass(frozen=True)
class ChargeState:
    """The derived effective state of one `cargo` (IC-03, IC-04).

    `estado` is the projection of the charge's `Confirmacion` rows;
    `confirmacion` is the row the projection came from, or `None` when the
    charge carries no row at all. Both are computed on read — no stored
    confirmation state exists on the charge or on the customer.

    `saldo` is what is still owed on the charge: `amount` minus every
    `Imputacion` against it. It is **derived on read**, never stored — there
    is no `pagado` column on a charge (ADR-27).
    """

    estado: ConfirmState
    confirmacion: Optional[ConfirmacionRow] = None
    saldo: Decimal = Decimal("0")

