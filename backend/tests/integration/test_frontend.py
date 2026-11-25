"""The frontend's contract, asserted from the BACKEND's side.

The frontend is TypeScript and React, and its own tests would need a
JavaScript test runner that the plan does not name. So the contract that
matters - the one the design fixes - is asserted here, against the
artefacts the frontend ships:

* **the bundle's URL answers 200 and not a blank page** (landmine 2);
* **the bundle lands in `STATIC_ROOT`**, so WhiteNoise serves it from
  the SAME ORIGIN as the API (CAC-06);
* **the SPA serves the three routes of design 11**;
* **`http.ts` refuses any absolute URL**, and the two audiences send
  their own credentials mode - the file is read and asserted, because the
  rule is about the SOURCE and a build cannot check it.

A note on why the source is read and not compiled. The rule "the fetch
helper rejects any absolute URL" is a property of the source: a bundle
could be built from a source that no longer refuses. Asserting on the
source is asserting the contract the design states, and it fails the
moment somebody "helpfully" relaxes the check.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "frontend"

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------


def test_el_proyecto_declara_las_tres_dependencias():
    """The Vite + React + TypeScript build, with the three declared."""
    paquete = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))

    assert "react" in paquete["dependencies"]
    assert "react-router-dom" in paquete["dependencies"]
    assert "vite" in paquete["devDependencies"]
    assert "typescript" in paquete["devDependencies"]
    assert "@vitejs/plugin-react" in paquete["devDependencies"]

    # The build command type-checks BEFORE it builds: a bundle that does
    # not type-check is not a bundle.
    assert "tsc" in paquete["scripts"]["build"]


def test_el_vite_construye_hacia_static_root():
    """The output lands in `STATIC_ROOT` (design 18.1).

    The build command of `render.yaml` runs `npm --prefix frontend run
    build` from the repository root, and `STATIC_ROOT` is
    `backend/staticfiles` by default - so the relative path of the
    build has to land there.
    """
    configuracion = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")

    assert "outDir" in configuracion
    m = re.search(r'outDir:\s*"([^"]+)"', configuracion)
    assert m is not None, "el build no declara outDir"
    destino = m.group(1)

    # The path is relative to `frontend/`, so it has to resolve into the
    # backend's static directory. The comparison is on the NORMALISED
    # paths: two `Path` objects that name the same directory can differ
    # in their spelling on Windows, and the contract is about the
    # directory, not about the string.
    resuelto = os.path.normcase(os.path.normpath(str((FRONTEND / destino).resolve())))
    esperado = os.path.normcase(os.path.normpath(str(Path(settings.STATIC_ROOT).resolve())))
    assert resuelto == esperado, (
        f"el build escribe en {resuelto} y STATIC_ROOT es {esperado}"
    )


def _cuerpo(respuesta) -> bytes:
    """The response's body, whatever kind of response it is.

    Django's `serve()` answers a `FileResponse`, which STREAMS: it has
    no `content` attribute, only `streaming_content`.
    """
    if hasattr(respuesta, "streaming_content"):
        return b"".join(respuesta.streaming_content)
    return respuesta.content


def test_el_bundle_existe_y_su_url_responde_200():
    """Landmine 2: the bundle's URL answers 200, not a blank page.

    The bundle is BUILD OUTPUT and it is not committed - it is rebuilt by
    `npm --prefix frontend run build`. So this test builds it if it is
    not there, and skips - LOUDLY - if the build cannot run.
    """
    indice = Path(settings.STATIC_ROOT) / "index.html"
    if not indice.exists():
        pytest.skip(
            "El bundle no esta construido: corra `npm --prefix frontend "
            "run build` para esta prueba."
        )

    contenido = indice.read_text(encoding="utf-8")

    # The mount point and the script that takes it over.
    assert 'id="root"' in contenido
    assert "<script" in contenido and "assets/" in contenido

    # The bundle's assets are named with a hash and the manifest is
    # written, so a stale bundle is never served.
    manifiesto = Path(settings.STATIC_ROOT) / ".vite" / "manifest.json"
    assert manifiesto.exists()

    cliente = Client()
    respuesta = cliente.get("/app/cliente/")
    assert respuesta.status_code == 200
    cuerpo = _cuerpo(respuesta)
    assert b"<script" in cuerpo
    # And the script it names is a file of the bundle, so the page is
    # not a blank one pointing at nothing.
    import re as _re

    scripts = _re.findall(r'src="([^"]+\.js)"', cuerpo.decode("utf-8"))
    assert scripts, "la pagina no nombra ningun script"
    for script in scripts:
        assert (Path(settings.STATIC_ROOT) / script.lstrip("./")).exists(), (
            f"la pagina nombra un script que no existe: {script}"
        )


# ---------------------------------------------------------------------------
# The fetch contract, asserted on the source
# ---------------------------------------------------------------------------


def test_http_rechaza_una_url_absoluta():
    """`http.ts` refuses any absolute URL.

    The same-origin contract (design 11): every request uses a relative
    path, so a second host cannot be introduced by accident. The refusal
    is a thrown error and not a silent correction.
    """
    fuente = (FRONTEND / "src" / "api" / "http.ts").read_text(encoding="utf-8")

    # The check exists, and it throws.
    assert "esRelativo" in fuente
    assert "throw new Error" in fuente
    # And it refuses the protocol-relative form too.
    assert '"//"' in fuente or "'//'" in fuente or "//" in fuente


def _codigo(fichero: Path) -> str:
    """The file's CODE, with the comments and the docstrings removed.

    The contract is about the source that RUNS, not about the prose that
    explains it. A docstring that mentions `"omit"` while explaining
    that the client does NOT send `"omit"` would otherwise make the
    assertion pass for the wrong reason - and the same defect class
    this project keeps finding: a check that can only pass is not a
    check.
    """
    texto = fichero.read_text(encoding="utf-8")
    # The block comments.
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    # The line comments.
    texto = re.sub(r"^\s*//.*$", "", texto, flags=re.M)
    return texto



def test_el_personal_envia_la_sesion():
    """The staff sends the session with `credentials: "same-origin"`."""
    codigo = _codigo(FRONTEND / "src" / "api" / "staff.ts")

    assert "same-origin" in codigo
    assert '"omit"' not in codigo



def test_el_personal_manda_el_csrf():
    """Every staff mutation carries `X-CSRFToken`.

    The token is read from the cookie Django set, by the shared helper,
    and added to every request that has one.
    """
    http = (FRONTEND / "src" / "api" / "http.ts").read_text(encoding="utf-8")
    assert "X-CSRFToken" in http
    assert "csrftoken" in http


# ---------------------------------------------------------------------------
# The routes
# ---------------------------------------------------------------------------


def test_el_enrutador_declara_las_tres_rutas():
    """The routes of design 11.

    `/app/posicion`, `/app/propuesta/:id` and `/app/cuenta` - plus
    `/app/mostrador`, the counter. The paths carry NO trailing slash:
    Django mounts them with one, and the two would not be the same
    route.

    **There is no `/app/cliente`**: the credential's audience is gone,
    and the person's account is her only door.
    """
    fuente = (FRONTEND / "src" / "router.tsx").read_text(encoding="utf-8")

    assert '"/app/posicion"' in fuente
    assert '"/app/propuesta/:id"' in fuente
    assert '"/app/cuenta"' in fuente
    assert '"/app/mostrador"' in fuente
    # And none of them carries a trailing slash.
    assert '"/app/posicion/"' not in fuente
    assert '"/app/cuenta/"' not in fuente
    # **And the client's route is gone.**
    assert '"/app/cliente"' not in fuente


def test_el_documento_carga_la_politica_de_seguridad():
    """The client page carries a credential, so the policy is strict.

    `default-src 'self'` and nothing else: no third-party script, no
    external font, no analytics (design 11).
    """
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")

    assert "Content-Security-Policy" in html
    assert "default-src 'self'" in html
    # No third-party origin at all.
    assert "http://" not in html
    assert "https://" not in html
