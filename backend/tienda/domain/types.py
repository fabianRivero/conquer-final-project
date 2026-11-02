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
`saldo`, no `status`, no `stock` and no stored confirmation state.

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

    `cargo` adds debt, `pago` retires it and `nota_credito` reduces it. The
    values are the exact strings the database `CHECK` accepts.
    """

    CARGO = "cargo"
    PAGO = "pago"
    NOTA_CREDITO = "nota_credito"


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
    """

    SIN_CONFIRMAR = "sin_confirmar"
    CONFIRMADO = "confirmado"
    EN_DISPUTA = "en_disputa"


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

    Mirrors `LedgerEntry` without touching the ORM: `kind`, `amount`,
    `occurred_at` and the optional `cargo` the note reconciles. `id` is the
    row's own identifier, which is the **tie-breaker** of the FIFO order of
    PA-02.
    """

    id: int
    kind: EntryKind
    amount: Decimal
    occurred_at: datetime
    cargo: Optional[int] = None


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
    which payment retired which charge. `residual` is the surplus that
    matched nothing — credit in the customer's favour, never an error. The
    `saldo` of each charge is what is still owed on it.
    """

    asignaciones: tuple[tuple[int, int, Decimal], ...] = ()
    residual: Decimal = Decimal("0")
    saldos: tuple[tuple[int, Decimal], ...] = ()


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

    Mirrors the table: `estado`, `importe_reclamado`, `confirmado_en` and the
    `id` that orders the history. `origen` records who appended the row.
    """

    id: int
    estado: ConfirmState
    importe_reclamado: Optional[Decimal] = None
    confirmado_en: Optional[datetime] = None
    origen: str = "cliente"


@dataclass(frozen=True)
class ChargeState:
    """The derived effective state of one `cargo` (IC-03, IC-04).

    `estado` is the projection of the charge's `Confirmacion` rows;
    `confirmacion` is the row the projection came from, or `None` when the
    charge carries no row at all. Both are computed on read — no stored
    confirmation state exists on the charge or on the customer.
    """

    estado: ConfirmState
    confirmacion: Optional[ConfirmacionRow] = None
