"""The design's route table, against the API's map.

**The design is the contract, and a contract that lies is not a
contract.** The design's Â§9.1 lists the routes that exist; a route that
the map declares and the table does not name is a route nobody decided
on, and a route the table names and the map does not declare is a
document describing something that does not exist.

**Why this is a test and not a reading.** The table drifted once: the
account rewrite added ten routes and the table never mentioned them, and
nothing failed. The test that existed then looked in ONE direction -
"every route of the design is declared" - and a route that appears
without being designed passes it. **This one looks in BOTH**, and it
compares the DOCUMENT, not a list written in the test: a list in the
test and the table in the document are two places to forget, and one of
them was always going to be the one that drifted.

The parameter names count too: the document writes `{pago_id}` and the
map says `<int:pago_id>`, and a person reading the design has to be
able to call the route it names.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DESIGN = REPO / "openspec" / "changes" / "fiado-confirmado" / "design.md"

pytestmark = pytest.mark.integration


def _seccion_de_rutas() -> str:
    """The Â§9.1 of the design - the route table."""
    texto = DESIGN.read_text(encoding="utf-8")
    inicio = texto.find("### 9.1 Routes")
    fin = texto.find("### 9.2", inicio)
    assert inicio >= 0 and fin > inicio, "the design has no section 9.1"
    return texto[inicio:fin]


def _a_patrono(ruta: str) -> str:
    """`{pago_id}` of the document is `<int:pago_id>` of the map."""
    return re.sub(
        r"\{([^}]+)\}",
        lambda m: "<int:%s>" % m.group(1).split(":")[0],
        ruta,
    )


def _rutas_de_la_tabla() -> set[str]:
    """The API routes the table names, in the map's own spelling."""
    return {
        _a_patrono(ruta).replace("/api/v1/", "", 1)
        for ruta in re.findall(r"`(/api/v1/[^`]+)`", _seccion_de_rutas())
    }


def _rutas_del_mapa() -> set[str]:
    """Every route the API declares."""
    from tienda.api import urls as urls_api

    return {_a_patrono(str(p.pattern)) for p in urls_api.urlpatterns}


def test_the_design_names_every_route_the_api_declares():
    """**Every route of the map is in the design's table.**

    A route that the map declares and the table does not name is a
    route nobody decided on.
    """
    sin_documentar = _rutas_del_mapa() - _rutas_de_la_tabla()

    assert sin_documentar == set(), (
        "the design does not describe these routes: "
        + ", ".join(sorted(sin_documentar))
    )


def test_the_design_names_no_route_that_does_not_exist():
    """**Every route of the table is in the map.**

    A route the design names and the API does not declare is a document
    describing something that does not exist.
    """
    inexistentes = _rutas_de_la_tabla() - _rutas_del_mapa()

    assert inexistentes == set(), (
        "the design names routes that do not exist: "
        + ", ".join(sorted(inexistentes))
    )


def test_the_table_names_the_routes_of_the_account_rewrite():
    """**The account rewrite's routes are in the table.**

    They are the ones that drifted: the person's account, her links, the
    counter's search and her answer to a fiado. A test that names them
    is a test that says where they belong.
    """
    tabla = _rutas_de_la_tabla()

    for esperado in (
        "mostrador/buscar/",
        "cuenta/registro/",
        "cuenta/login/",
        "cuenta/logout/",
        "perfiles/",
        "perfiles/cliente/",
        "perfiles/tienda/",
        "cuenta/vinculos/",
        "cuenta/vinculos/aceptar/",
        "cuenta/vinculos/rechazar/",
        "cuenta/fiados/",
        "cuenta/fiados/aceptar/",
        "cuenta/fiados/rechazar/",
        "cuenta/cargos/",
        "tienda/login/",
        "tienda/personal/",
        "tienda/vinculos/",
    ):
        assert esperado in tabla, (
            f"the design's table does not name {esperado}"
        )


def test_the_parameter_names_of_the_table_are_the_ones_of_the_map():
    """**The names match too.**

    The design writes `{pago_id}` and the map says `<int:pago_id>`. A
    person reading the design has to be able to call the route it
    names, and `{id}` next to `<int:pago_id>` is a route nobody can
    call.
    """
    seccion = _seccion_de_rutas()

    # Los nombres de los parametros nombres_mapa.
    nombres_mapa = {
        re.search(r"<int:(\w+)>", patron).group(1)
        for patron in _rutas_del_mapa()
        if "<int:" in patron
    }

    # Los que nombra el documento.
    nombres_documento = set()
    for ruta in re.findall(r"`(/api/v1/[^`]+)`", seccion):
        for nombre in re.findall(r"\{(\w+)\}", ruta):
            nombres_documento.add(nombre)

    # Los nombres genericos - `{id}` - son los que no coinciden.
    genericos = {"id"}

    assert not (nombres_documento & genericos) or (
        nombres_documento - genericos
    ) <= nombres_mapa | genericos, (
        "the design names parameters the map does not have: "
        + ", ".join(sorted(nombres_documento - nombres_mapa - genericos))
    )

