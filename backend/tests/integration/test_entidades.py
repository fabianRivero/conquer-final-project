"""The design's entity table, against the models.

**The design is the contract, and a contract that lies is not a
contract.** The design's §2 lists the entities that exist; an entity the
code has and the table does not name is a model nobody decided on, and
an entity the table names and the code does not have is a document
describing something that does not exist.

**Why this is a test and not a reading.** The table drifted three times
and nothing failed. The account rewrite (10.3) added `Vinculo` and the
table never mentioned it -- the model the whole rewrite is built on,
absent from the table of models. The 10.6 removed `CustomerCodigo` and
`CodigoIntento` and the table kept them, with their constraints, their
error codes and their columns. And `Customer` kept claiming a `Shop`
and a `credit_limit` that it had not had since the 10.4.

**It looks in BOTH directions, and it compares the DOCUMENT.** A list
written in the test and the table in the document are two places to
forget, and one of them was always going to be the one that drifted.

**The count is checked too.** "Sixteen entities" was true once and
stopped being true, and a number in a document does not correct itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DESIGN = REPO / "openspec" / "changes" / "fiado-confirmado" / "design.md"

pytestmark = pytest.mark.integration


def _seccion_del_modelo() -> str:
    """The §2 of the design - the entity table and its notes."""
    texto = DESIGN.read_text(encoding="utf-8")
    inicio = texto.find("### 2.")
    fin = texto.find("### 3.", inicio)
    assert inicio >= 0 and fin > inicio, "the design has no section 2"
    return texto[inicio:fin]


def _entidades_de_la_tabla() -> set[str]:
    """The entities the table names, without the backticks.

    **Only the entity table.** The section carries other tables too - the
    domain functions, the transactional rules - and their rows are not
    entities.
    """
    nombres = set()
    dentro = False
    for linea in _seccion_del_modelo().splitlines():
        if linea.startswith("| Entity |"):
            dentro = True
            continue
        if not dentro:
            continue
        if not linea.startswith("|"):
            break
        celdas = linea.split("|")
        if len(celdas) < 3:
            continue
        # Las filas de nota llevan un asterisco de "conditional" DETRAS del
        # nombre (`StockMovement` *), asi que el asterisco se va antes que
        # las comillas invertidas.
        nombre = celdas[1]
        for caracter in ("*", "\\", "`", " "):
            nombre = nombre.strip().strip(caracter)
        if nombre and set(nombre) != {"-"}:
            nombres.add(nombre)
    return nombres


def _entidades_del_codigo() -> set[str]:
    """Every concrete model of the app."""
    from django.apps import apps

    return {
        modelo.__name__
        for modelo in apps.get_models()
        if modelo._meta.app_label == "tienda"
    }


def test_la_tabla_nombra_todas_las_entidades_del_codigo():
    """**Every model the code has is in the table.**

    A model the code has and the table does not name is a model nobody
    decided on. `Vinculo` was one for three slices.
    """
    sin_documentar = _entidades_del_codigo() - _entidades_de_la_tabla()

    assert sin_documentar == set(), (
        "the design's table does not describe these entities: "
        + ", ".join(sorted(sin_documentar))
    )


def test_la_tabla_no_nombra_entidades_que_no_existen():
    """**Every entity of the table is in the code.**

    An entity the table names and the code does not have is a document
    describing something that does not exist. `CustomerCodigo` and
    `CodigoIntento` were two for a whole release.
    """
    inexistentes = _entidades_de_la_tabla() - _entidades_del_codigo() - {"User"}

    assert inexistentes == set(), (
        "the design's table names entities that do not exist: "
        + ", ".join(sorted(inexistentes))
    )


def test_el_recuento_de_entidades_es_el_que_dice():
    """**The number in the document is the number of entities.**

    "Sixteen entities" was true once. A count in a document does not
    correct itself, and a reader who counts seventeen and reads
    sixteen stops trusting the rest.
    """
    seccion = _seccion_del_modelo()
    encontrado = re.search(r"\*\*(\w+) entities\*\*", seccion)

    assert encontrado is not None, (
        "the design's §2 does not say how many entities it has"
    )

    recuento = encontrado.group(1).lower()
    expected = {
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
    }

    assert recuento in expected, f"the document says '{recuento}' entities"

    assert expected[recuento] == len(_entidades_del_codigo()), (
        f"the design says {recuento} entities and the code has "
        f"{len(_entidades_del_codigo())}"
    )


def test_la_tabla_no_declara_una_tienda_que_el_cliente_no_tiene():
    """**`Customer` has no shop, and no `credit_limit`.**

    The 10.4 took both away: the limit moved to the link and the person
    belongs to no shop. The row kept saying otherwise for a whole
    release.
    """
    fila = None
    for linea in _seccion_del_modelo().splitlines():
        if linea.startswith("| `Customer` |"):
            fila = linea
            break

    assert fila is not None, "the design's table has no `Customer` row"

    assert "`Shop` CASCADE" not in fila, (
        "the `Customer` row claims a shop: the customer belongs to no shop"
    )
    assert "credit_limit" not in fila, (
        "the `Customer` row claims a `credit_limit`: the limit is the LINK's"
    )
    assert "user_id" in fila, (
        "the `Customer` row does not name the person behind the row"
    )
