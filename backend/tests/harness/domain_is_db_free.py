"""The DB-free harness of the domain layer — run OUTSIDE pytest.

This is the runtime harness of Phase 3. It proves the guarantee from the
outside: the domain package is imported and every rule is exercised with
**no Django settings configured** and **no database**.

It is deliberately a standalone script rather than a pytest module. Inside
pytest-django, the settings are configured and the `django_db` marker is
what forbids the database; here there is no pytest at all, so the absence of
a database is a property of the run itself.

    python backend/tests/harness/domain_is_db_free.py

The script fails loudly — a non-zero exit — if any rule needs Django or a
database.
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# The `backend` directory, so that the `tienda` package is importable.
# `parents[2]` is `backend` itself: this file lives at
# `backend/tests/harness/domain_is_db_free.py`.
BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

# Nothing from the environment: no DATABASE_URL, no SECRET_KEY.
for variable in ("DATABASE_URL", "SECRET_KEY", "DEBUG", "ALLOWED_HOSTS"):
    os.environ.pop(variable, None)

# The proof that the domain layer never reads the Django settings. Django
# is installed on this host, so the check is not "is Django importable" but
# "did the domain layer ask for the settings".
#
# `settings.configured` is read **before** the rules run, and again after.
# Importing `django.conf` does not configure anything on its own — only
# touching `settings.SOMETHING` does — so the flag stays False unless a
# rule reached for it.
from django.conf import settings as django_settings  # noqa: E402

if django_settings.configured:
    raise SystemExit(
        "FAIL: Django settings were already configured before the domain "
        "layer ran; the harness is not measuring what it claims."
    )


from tienda.domain.ageing import age_in_days, bucket_of  # noqa: E402
from tienda.domain.allocation import allocate_payments, imputations_of  # noqa: E402
from tienda.domain.cash import caja_al_cierre, desviacion_cierre  # noqa: E402
from tienda.domain.charges import (  # noqa: E402
    charge_amount_matches,
    precio_unitario_de,
    propuesta_amount_matches,
    total_de_linea,
)
from tienda.domain.confirmation import (  # noqa: E402
    confirmacion_efectiva,
    confirmacion_requerida,
    estado_cargo,
    propuesta_transicion_permitida,
)
from tienda.domain.evaluation import antiguedad_max_dias, evaluate_customer  # noqa: E402
from tienda.domain.position import cash_at, outstanding, real_position  # noqa: E402
from tienda.domain.stock import existencias_registradas  # noqa: E402
from tienda.domain.types import (  # noqa: E402
    CashLine,
    CargoLine,
    ConfirmacionRow,
    ConfirmState,
    EntryKind,
    LedgerLine,
    MovementKind,
    PropuestaEstado,
    StockLine,
)

BASE = datetime(2026, 3, 1, 9, 0, 0)
DIA = timedelta(days=1)


def cargo(identificador, importe, dias=0):
    return LedgerLine(
        id=identificador,
        kind=EntryKind.CARGO,
        amount=Decimal(importe),
        occurred_at=BASE - dias * DIA,
    )


def pago(identificador, importe, dias=0):
    return LedgerLine(
        id=identificador,
        kind=EntryKind.PAGO,
        amount=Decimal(importe),
        occurred_at=BASE - dias * DIA,
    )


def comprobar(condicion, mensaje):
    if not condicion:
        raise SystemExit(f"FAIL: {mensaje}")


# 1. The outstanding. A payment that fits leaves nothing owed. There is no
# `credit_a_favor` state any more: rule 19 refuses a `pago` larger than the
# debt it retires, and the excess leaves the counter as change.
comprobar(
    outstanding([cargo(1, "20.00"), pago(2, "20.00")], BASE) == Decimal("0"),
    "the outstanding must report nothing owed after a payment that fits",
)
comprobar(
    outstanding([cargo(1, "20.00"), cargo(2, "10.00")], BASE) == Decimal("30.00"),
    "the outstanding must be the sum of the charges",
)

# 2. The real position, additive only.
comprobar(
    real_position(Decimal("190.00"), Decimal("21.00")) == Decimal("211.00"),
    "the real position must be the sum of the drawer and the balances",
)

# 3. The cash.
comprobar(
    cash_at(
        Decimal("50.00"),
        [CashLine(1, MovementKind.ENTRADA, Decimal("100.00"), BASE)],
        [pago(10, "50.00", 1)],
        BASE,
    )
    == Decimal("200.00"),
    "the cash must be the opening plus the movements plus the payments",
)

# 4. The FIFO allocation. The charges are 19 days and 0 days old, and the
# payment arrives 25 days ago — **before** both of them. A payment may only
# retire a charge that is at least as old as the payment itself, so the
# money matches nothing.
asignacion = allocate_payments(
    [cargo(1, "10.00", 19), cargo(2, "40.00", 0)], [pago(10, "30.00", 25)]
)
comprobar(
    dict(asignacion.saldos) == {1: Decimal("10.00"), 2: Decimal("40.00")},
    "a payment that predates every charge must retire none of them",
)

# The same charges, with the payment arriving after them: now the money
# retires the oldest charge first.
asignacion_tardia = allocate_payments(
    [cargo(1, "10.00", 19), cargo(2, "40.00", 0)], [pago(10, "30.00", 0)]
)
comprobar(
    dict(asignacion_tardia.saldos) == {1: Decimal("0"), 2: Decimal("20.00")},
    "the allocation must retire the oldest charge first",
)
comprobar(
    asignacion_tardia.residual == Decimal("0"),
    "a payment that fits must leave no residual",
)

# 4b. The repartition. A payment of 20,00 € against charges of 8,00 €, 7,00 €
# and 15,00 € writes three imputations — 8,00, 7,00 and 5,00 — and the
# charges read 8/8, 7/7 and 5/15. The grain is the charge.
reparto = allocate_payments(
    [cargo(1, "8.00", 2), cargo(2, "7.00", 1), cargo(3, "15.00", 0)],
    [pago(10, "20.00", 0)],
)
imputaciones = imputations_of(reparto, 10)
comprobar(
    [(i.cargo_id, i.importe) for i in imputaciones]
    == [(1, Decimal("8.00")), (2, Decimal("7.00")), (3, Decimal("5.00"))],
    "the repartition must record one imputation per charge, by the charge",
)
comprobar(
    dict(reparto.saldos) == {1: Decimal("0"), 2: Decimal("0"), 3: Decimal("10.00")},
    "the charges must read 8/8, 7/7 and 5/15 after a payment of 20,00",
)

# 5. The ageing.
comprobar(age_in_days(BASE - 8 * DIA, BASE) == 8, "the age must be 8 days")
comprobar(
    bucket_of(7).value == "vigente" and bucket_of(8).value == "envejecido",
    "the bucket boundary 7/8 must hold",
)

# 6. The evaluation.
estado = evaluate_customer(
    [cargo(1, "10.00", 45)], credit_limit=None, at=BASE
)
comprobar(estado.suspendido is True, "a 45-day debt must suspend the customer")
comprobar(
    evaluate_customer(
        [cargo(1, "1000000.00", 1)], credit_limit=None, at=BASE
    ).suspendido
    is False,
    "a null credit limit must never fire limite_superado",
)
comprobar(
    evaluate_customer(
        [cargo(1, "10.00", 45)], credit_limit=None, at=BASE, override=True
    ).suspendido
    is False,
    "the override must lift the automatic suspension",
)
comprobar(
    antiguedad_max_dias([cargo(1, "20.00", 45)], [pago(10, "20.00", 1)], BASE) == 0,
    "a retired debt must have no age",
)

# 7. The charges. The itemisation is mandatory: a line-less charge matches
# **no** amount, and a proposal with no lines matches no total.
comprobar(
    total_de_linea(Decimal("2.5"), Decimal("1.25")) == Decimal("3.13"),
    "the line total must round half up to two decimals",
)
comprobar(
    precio_unitario_de(Decimal("1.20"), Decimal("1.00")) == Decimal("1.00"),
    "the override must win over the catalogue price",
)
comprobar(
    charge_amount_matches([], Decimal("4.20")) is False,
    "a line-less charge must match no declared amount",
)
comprobar(
    charge_amount_matches(
        [CargoLine(1, Decimal("1"), Decimal("4.20"), Decimal("4.20"))],
        Decimal("4.20"),
    )
    is True,
    "a charge whose lines add up must match its declared amount",
)
comprobar(
    propuesta_amount_matches([], Decimal("4.20")) is False,
    "a proposal with no lines must match no total",
)

# 8. The confirmation. The state machine has one state and the proposal
# transition is one-way.
filas = [ConfirmacionRow(1, ConfirmState.CONFIRMADO, BASE - 10 * DIA)]
comprobar(
    confirmacion_efectiva(filas).id == 1,
    "the effective confirmation must be the row",
)
comprobar(
    estado_cargo(filas).estado is ConfirmState.CONFIRMADO,
    "the effective state must follow the row",
)
comprobar(
    confirmacion_requerida(charge_exists=False, confirmation_rows=[]) is True,
    "a charge that does not exist yet may be written with its confirmation",
)
comprobar(
    confirmacion_requerida(charge_exists=True, confirmation_rows=[]) is False,
    "a charge without a confirmation must be refused",
)
comprobar(
    propuesta_transicion_permitida(
        PropuestaEstado.PENDIENTE, PropuestaEstado.CONFIRMADO
    )
    is None,
    "a pending proposal may be confirmed",
)
comprobar(
    propuesta_transicion_permitida(
        PropuestaEstado.CONFIRMADO, PropuestaEstado.CONFIRMADO
    )
    is not None,
    "a confirmed proposal may not be confirmed again",
)
comprobar(
    propuesta_transicion_permitida(
        PropuestaEstado.CANCELADO, PropuestaEstado.CANCELADO
    )
    is not None,
    "a cancelled proposal may not be cancelled again",
)

# 9. The stock.
figura, qualifier = existencias_registradas(
    [
        StockLine(1, MovementKind.ENTRADA, Decimal("10.00"), BASE),
        StockLine(2, MovementKind.SALIDA, Decimal("3.00"), BASE),
    ]
)
comprobar(figura == Decimal("7.00"), "the stock must be the entries minus the exits")
comprobar(
    qualifier.value == "techo_no_conteo",
    "the stock must carry the techo_no_conteo qualifier",
)

# 10. The close.
comprobar(
    caja_al_cierre(Decimal("75.00"), [], [], BASE) == Decimal("75.00"),
    "the close must derive the expected cash",
)
comprobar(
    desviacion_cierre(Decimal("190.00"), Decimal("188.50")) == Decimal("1.50"),
    "the deviation must be the expected minus the counted",
)

# The final proof: the rules ran and Django was **never** configured, which
# means no rule read a setting and no rule could have opened a database
# connection — a connection needs a configured engine.
if django_settings.configured:
    raise SystemExit(
        "FAIL: the domain layer configured Django settings; a rule reached "
        "for the framework."
    )

# And the database is proven unreachable, not merely unused.
try:
    from django.db import connection

    connection.ensure_connection()
    raise SystemExit("FAIL: the domain layer opened a database connection.")
except ImportError:
    pass
except Exception as exc:
    # The only acceptable failure here is "there is no configured engine" —
    # anything else would mean the layer reached for a database.
    if "settings" not in str(exc).lower() and "configured" not in str(exc).lower():
        raise SystemExit(f"FAIL: the domain layer touched the database: {exc!r}")

print("OK: 21 rules exercised with no Django settings and no database.")
