"""The derived state of a customer: the debt, the suspension and its cause.

PA-05 and PA-06 ask for two things, and this module provides exactly them.

**The suspension is automatic and computed on read.** A customer is
`suspendido` when the oldest unpaid charge is older than the suspension age,
or when the outstanding exceeds the credit limit. No human action is
required to suspend, and none is required to lift it either — an
`override=True` lifts the automatic suspension, and the override is itself an
appended act recorded by the service layer (PA-08).

**The credit limit is an explicit state.** `credit_limit=None` means
«sin límite». It never fires `limite_superado`: a customer without a limit
can owe as much as the shop allows, and only the age of the debt can suspend
them.

Nothing here is stored. `Customer` has no `status` column and no
`suspended_reason` column (D1) — this module is where those two answers come
from.

The v1 module carried the dispute case: a charge under an open dispute was
still debt, and a `nota de crédito` cancelled it. Both are gone with the
dispute machinery — the client confirms the charge before it exists, so
there is nothing to dispute and nothing to reconcile (ADR-18, ADR-19).
"""

from __future__ import annotations

from decimal import Decimal

from .ageing import age_in_days
from .allocation import allocate_payments
from .types import CustomerState, EntryKind, LedgerLine, SuspensionReason

# The default age at which a debt suspends the customer (PA-06).
ANTIGUEDAD_SUSPENSION_DIAS = 30


def antiguedad_max_dias(charges, payments, at) -> int:
    """The age of the oldest **unpaid** charge, in days.

    The age of the oldest charge that still owes something. A charge that a
    payment has retired is not counted — the payment retires the debt, and a
    retired debt does not age.

    Zero means nothing is owed. The figure drives both the automatic
    suspension (PA-06) and the order of the risk ladder (PA-03).

    The signature is the one design §10 fixes: three arguments, charges and
    payments and the instant. There is no third kind of money any more — the
    credit note is gone.
    """
    unpaid = _unpaid_charges(charges, payments, at)
    if not unpaid:
        return 0
    return max(age_in_days(cargo.occurred_at, at) for cargo in unpaid)


def evaluate_customer(
    lines,
    *,
    credit_limit,
    at,
    suspension_age_days: int = ANTIGUEDAD_SUSPENSION_DIAS,
    override: bool = False,
) -> CustomerState:
    """The derived state of a customer at `at`.

    `lines` are the customer's ledger lines — `cargo` and `pago` alike.
    `credit_limit` is the explicit limit, or `None` for «sin límite». `at` is
    the instant the question is asked; there is no implicit clock.
    `suspension_age_days` is the age at which the debt suspends the
    customer, 30 days by default. `override` is the owner's lifted
    suspension.

    The result reports:

    * `total` — the outstanding, derived from the lines alone;
    * `antiguedad_max_dias` — the age of the oldest unpaid charge;
    * `suspendido` and `motivo` — the derived flag and its cause.

    The cause is `LIMITE_SUPERADO` when the outstanding exceeds the limit,
    `ANTIGUEDAD_SUPERADA` when the oldest unpaid charge is older than the
    suspension age, and `None` when the customer is active. When both causes
    apply, the limit is reported: it is the one the owner can act on
    immediately, while the age passes on its own.

    `credit_limit=None` **never** fires `LIMITE_SUPERADO`. `override=True`
    lifts the automatic suspension entirely: the customer reads active even
    when both causes apply.

    **The outstanding is never negative.** A `pago` never exceeds the debt it
    retires (rule 19): the shop returns the excess as change and it never
    enters the book, so there is no credit to hold and no `credit_a_favor`
    state (ADR-26).
    """
    cargos = [line for line in lines if line.kind == EntryKind.CARGO]
    pagos = [line for line in lines if line.kind == EntryKind.PAGO]

    total = _total(cargos, pagos, at)
    antiguedad = _antiguedad(cargos, pagos, at)

    motivo: SuspensionReason | None = None

    # The limit only exists when the owner set one. `None` is «sin límite»,
    # an explicit state and never a missing value (PA-05).
    if credit_limit is not None and total > Decimal(credit_limit):
        motivo = SuspensionReason.LIMITE_SUPERADO
    elif antiguedad > suspension_age_days:
        motivo = SuspensionReason.ANTIGUEDAD_SUPERADA

    # The owner's override lifts the automatic suspension. It is an appended
    # act, and it rewrites no entry (PA-08).
    if override:
        motivo = None

    return CustomerState(
        alias="",
        total=total,
        antiguedad_max_dias=antiguedad,
        suspendido=motivo is not None,
        motivo=motivo,
        credit_limit=None if credit_limit is None else Decimal(credit_limit),
    )


def _antiguedad(cargos, pagos, at) -> int:
    """The age of the oldest charge that still owes something."""
    unpaid = _unpaid_charges(cargos, pagos, at)
    if not unpaid:
        return 0
    return max(age_in_days(cargo.occurred_at, at) for cargo in unpaid)


def _unpaid_charges(charges, payments, at) -> list:
    """The charges that still owe something at `at`.

    The allocation decides which charges the money retired, and a charge that
    is left with a zero balance is not counted. A charge dated after `at` has
    not happened yet and is not counted either.

    There is no third kind of money: the v1 version applied the credit notes
    here, and they are gone with the dispute machinery.
    """
    a_tenor = [c for c in charges if c.occurred_at <= at]
    pago_a_tenor = [p for p in payments if p.occurred_at <= at]

    if not a_tenor:
        return []

    resultado = allocate_payments(a_tenor, pago_a_tenor)
    saldos = dict(resultado.saldos)
    return [c for c in a_tenor if saldos.get(c.id, Decimal("0")) > 0]


def _total(cargos, pagos, at) -> Decimal:
    """`Σ cargos − Σ pagos` over the entries at or before `at`.

    No third term: there is no `nota de crédito` any more, and no customer
    credit — a `pago` never exceeds the debt it retires (rule 19).
    """
    total = Decimal("0")
    for cargo in cargos:
        if cargo.occurred_at <= at:
            total += cargo.amount
    for pago in pagos:
        if pago.occurred_at <= at:
            total -= pago.amount
    return total

