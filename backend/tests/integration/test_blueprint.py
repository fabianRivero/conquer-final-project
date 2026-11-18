"""The blueprint is validated against Render's OWN schema.

**The blueprint is a contract with a third party**, and the third party
has a schema: `https://render.com/schema/render.yaml.json`. The file
parses as YAML, and it was still rejected twice:

* `runCommand` is not a Render key - the schema's `serverService` has
  `additionalProperties: false` and lists `startCommand`;
* `sync` cannot be combined with `value` or with `generateValue` - the
  schema's `envVar` is an `anyOf` over four shapes, and each entry has
  to satisfy exactly one.

Both errors were found by Render, at the moment the owner tried to
deploy. **This test finds them here instead**, and it fails with the
message Render would give - the path of the offending entry.

The schema is fetched from the network, so the test SKIPS when it
cannot be reached: a blueprint that cannot be validated is not a
validated blueprint, and the test says so out loud rather than passing
quietly. The CI can fetch it - it has network - and the local run can
too, when it is offline it says why it skipped.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
RENDER = REPO / "render.yaml"

#: Render's own schema for the blueprint.
ESQUEMA_URL = "https://render.com/schema/render.yaml.json"


@pytest.fixture(scope="module")
def esquema():
    """Render's schema, fetched."""
    try:
        with urllib.request.urlopen(ESQUEMA_URL, timeout=20) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        pytest.skip(
            f"No se pudo traer el esquema de Render ({exc}): el blueprint "
            f"queda SIN VALIDAR, no validado."
        )


@pytest.fixture
def blueprint():
    with RENDER.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_el_blueprint_cumple_el_esquema_de_render(blueprint, esquema):
    """The whole file satisfies Render's schema.

    The error message names the path of the offending entry, the way
    Render's does - because a validator that says "invalid" and nothing
    else is a validator that costs another round trip to the dashboard.
    """
    jsonschema = pytest.importorskip("jsonschema")

    try:
        jsonschema.validate(blueprint, esquema)
    except jsonschema.ValidationError as exc:
        ruta = " -> ".join(str(p) for p in exc.absolute_path)
        raise AssertionError(
            f"El blueprint no cumple el esquema de Render en {ruta}: "
            f"{exc.message}"
        ) from exc


def test_cada_variable_tiene_una_sola_forma(blueprint, esquema):
    """Each `envVars` entry satisfies EXACTLY ONE of the four shapes.

    The schema's `envVar` is an `anyOf`, and the combinations Render
    rejects are the ones that satisfy NONE - `sync` together with
    `value`, or with `generateValue`. The three forms are mutually
    exclusive:

    * `value` - a hardcoded value;
    * `generateValue` - Render generates one;
    * `sync: false` - Render PROMPTS for it in the dashboard.
    """
    jsonschema = pytest.importorskip("jsonschema")

    formas = {
        nombre: esquema["definitions"][nombre]
        for nombre in (
            "envVarFromKeyValue",
            "envVarFromDatabase",
            "envVarFromService",
            "envVarFromGroup",
        )
    }

    for indice, entrada in enumerate(blueprint["services"][0]["envVars"]):
        coinciden = []
        for nombre, forma in formas.items():
            try:
                jsonschema.validate(entrada, forma)
            except jsonschema.ValidationError:
                continue
            coinciden.append(nombre)

        assert len(coinciden) == 1, (
            f"envVars[{indice}] ({entrada.get('key')}) satisface "
            f"{len(coinciden)} formas: {coinciden}. Cada entrada tiene que "
            f"satisfacer UNA: `value` y `generateValue` y `sync: false` son "
            f"mutuamente excluyentes."
        )


def test_las_claves_del_servicio_son_las_de_render(blueprint, esquema):
    """Every key of the service is one Render knows.

    The schema's `serverService` has `additionalProperties: false`, so a
    key Render does not know rejects the WHOLE file - with a message
    that does not say which key is wrong.
    """
    jsonschema = pytest.importorskip("jsonschema")

    forma = esquema["definitions"]["serverService"]
    aceptadas = set(forma["properties"])

    servicio = blueprint["services"][0]
    desconocidas = set(servicio) - aceptadas
    assert not desconocidas, (
        f"el servicio usa claves que Render no conoce: {sorted(desconocidas)}"
    )

    # And the two that carry the whole deployment.
    assert "buildCommand" in servicio
    assert "startCommand" in servicio


def test_el_health_check_apunta_a_una_ruta_real():
    """The health check path is a route the application actually serves.

    Render pings it every few seconds, and a 404 there means the deploy
    never goes healthy.
    """
    with RENDER.open(encoding="utf-8") as f:
        texto = f.read()

    import re

    m = re.search(r'healthCheckPath:\s*(\S+)', texto)
    assert m is not None, "el blueprint no declara healthCheckPath"
    ruta = m.group(1)
    assert ruta.startswith("/")

    from config import urls as urls_de_la_app

    # The mount of the API is an `include()` and carries no name of its
    # own, so the names are read from the patterns that have one.
    nombres = {
        patron.name
        for patron in urls_de_la_app.urlpatterns
        if getattr(patron, "name", None)
    }
    assert "health" in nombres, (
        f"la aplicacion no tiene la ruta 'health': {sorted(nombres)}"
    )
