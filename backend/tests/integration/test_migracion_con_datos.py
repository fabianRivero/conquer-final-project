"""The migration of the Slice 10.2, applied against a database that has
**the demo's data**.

**The bug this file pins.** The `0004` was **atomic**, and its
`RunPython` WRITES rows into `tienda_perfiltienda`: it creates the
business profile of every shop that has staff.

PostgreSQL refuses to `CREATE INDEX` while the transaction has pending
trigger events - and the rows the `RunPython` wrote are exactly that.
So the index of the FK that `AddField('perfiltienda.shop')` adds could
not be created, and the whole migration rolled back:

    cannot CREATE INDEX "tienda_perfiltienda" because it has pending
    trigger events

**Why it passed locally and failed on the deploy.** The local database
had **no shop with staff**: the `RunPython` found nothing to write, so
there were no pending trigger events and the index was created without
trouble. Neon had the demo data - the shop WITH its staff - so the
`RunPython` wrote, and the index could not be created.

**A migration is not proved by a database that has nothing in it.** The
data is the part that can break it, and a database with no data proves
nothing about the data.

The `0005` and the `0006` already run with `atomic = False` for exactly
this reason. The `0004` is the one that was left atomic, and it is the
one that fails.

**How this test is written.** It cannot run the real migration inside
the test transaction - the schema is already at the latest state. So it
asserts the thing that decides: **the migration is not atomic**. An
atomic migration that writes rows and then creates an index is the
defect; a non-atomic one has each operation in its own transaction, and
the index is created with no pending trigger events.
"""

from __future__ import annotations

import importlib

import pytest


def _modulo(nombre):
    return importlib.import_module(f"tienda.migrations.{nombre}")


def test_el_0004_no_es_atomico():
    """**The migration runs OUTSIDE a transaction.**

    A `RunPython` that writes rows, followed by a schema operation that
    creates an index, cannot live in ONE transaction: PostgreSQL refuses
    the index while the writes have pending trigger events.

    This is the assertion that decides the whole defect, and it is
    cheap: the behaviour it guards is the behaviour of PostgreSQL, not
    of Django.
    """
    mod = _modulo("0004_miembro_de_tienda")

    assert mod.Migration.atomic is False, (
        "el 0004 es atomico y su RunPython escribe filas: el indice del "
        "FK no se podra crear con los trigger events pendientes"
    )


@pytest.mark.parametrize(
    "nombre",
    [
        "0004_miembro_de_tienda",
        "0005_vinculo_con_consentimiento",
        "0006_customer_es_la_persona",
    ],
)
def test_las_migraciones_con_datos_no_son_atomicas(nombre):
    """**Every migration that writes rows is not atomic.**

    The three that move data - the staff become memberships, the
    customers become links, and the rows get linked to the person - all
    write. All three have to run outside the transaction, or the index
    that follows their writes cannot be created.
    """
    mod = _modulo(nombre)

    assert mod.Migration.atomic is False, (
        f"{nombre} escribe filas y es atomico: el deploy se rompe"
    )
