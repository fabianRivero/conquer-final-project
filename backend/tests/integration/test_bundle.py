"""The bundle is SERVED - landmine 2.

**"The bundle URL must return 200, not a blank page."** The page and
the asset are two different requests, and the page can answer 200 while
the asset answers 404: the page loads and the application never boots.

The cause was the manifest. The production static files storage
(`CompressedManifestStaticFilesStorage`) serves STRICTLY from the
`staticfiles.json` that `collectstatic` writes, and the Vite bundle is
not in `STATICFILES_DIRS` - `collectstatic` does not know about it, so
the bundle's assets are not in the manifest. With
`WHITENOISE_AUTOREFRESH` off - the production setting - the asset
answered **404**.

So the bundle's assets are served BY THE APPLICATION, out of `STATIC_ROOT`
and by name, and the bundle's base is `/` so the URLs do not depend on
the page's route.

**The test FAILS when the bundle is missing; it never skips.** A test
that can skip is a test that can prove nothing, and a skipped test
exits with the code of a pass - which is how the first version of this
test managed to be vacuous: the probe broke the route, the build in the
scratch copy failed because it had no `node_modules`, the test SKIPPED,
and the probe read the skip as a pass.

The bundle is built by the CI - `npm --prefix frontend run build` - and
the CI runs it before the suites. So the bundle's presence is a
precondition of the suite and not an optional extra.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from django.conf import settings

pytestmark = pytest.mark.integration

#: The port the local server answers on. It is a high one, out of the way
#: of anything else on the machine.
PUERTO = 8897


def _bundle_construido():
    """The bundle in `STATIC_ROOT`, or a failure.

    The bundle is BUILD OUTPUT and the CI builds it before the suites.
    If it is not there, the SUITE is not running in the right order, and
    that is a failure to report - not a reason to skip.
    """
    raiz = Path(settings.STATIC_ROOT)
    indice = raiz / "index.html"
    if not indice.exists():
        pytest.fail(
            f"El bundle no esta construido en {raiz}. El CI lo construye "
            f"antes de las suites: `npm --prefix frontend run build`."
        )
    return raiz


def test_el_bundle_se_sirve_y_su_asset_responde_200(db):
    """The page answers 200 AND the asset it names answers 200.

    The two are different requests, and the bug was in the second one:
    the page loaded and the application could never boot.
    """
    raiz = _bundle_construido()

    html = (raiz / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r'src="([^"]+\.js)"', html)
    assert scripts, "la pagina no nombra ningun script"

    # The manifest does NOT know the bundle - that is WHY the
    # application serves it. And the asset's URL is absolute, so it does
    # not depend on the page's route.
    assert scripts[0].startswith("/"), (
        f"el asset se pide en {scripts[0]!r}: la URL no debe depender de "
        f"la ruta de la pagina"
    )
    manifiesto = raiz / "staticfiles.json"
    if manifiesto.exists():
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
        for script in scripts:
            assert script.lstrip("/") not in datos.get("paths", {}), (
                "el bundle esta en el manifiesto: la prueba ya no prueba "
                "el camino que lo lleva"
            )

    # And the server answers the asset with 200.
    entorno = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "DEBUG": "False",
        "SECURE_SSL_REDIRECT": "0",
        "ALLOWED_HOSTS": "127.0.0.1",
    }
    servidor = subprocess.Popen(
        [
            sys.executable,
            "manage.py",
            "runserver",
            f"127.0.0.1:{PUERTO}",
            "--noreload",
        ],
        cwd=str(settings.BASE_DIR),
        env=entorno,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        listo = False
        for _ in range(40):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{PUERTO}/health/", timeout=2
                ).read()
                listo = True
                break
            except Exception:
                continue

        assert listo, "el servidor local no arranco"

        pagina = urllib.request.urlopen(
            f"http://127.0.0.1:{PUERTO}/app/cliente/", timeout=5
        )
        assert pagina.status == 200

        for script in scripts:
            try:
                respuesta = urllib.request.urlopen(
                    f"http://127.0.0.1:{PUERTO}{script}", timeout=5
                )
            except urllib.error.HTTPError as exc:
                raise AssertionError(
                    f"el asset {script} responde {exc.code}: la pagina "
                    f"carga pero la aplicacion no arranca"
                ) from exc
            assert respuesta.status == 200
            assert len(respuesta.read()) > 1000, (
                f"el asset {script} viene vacio"
            )
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=5)
        except Exception:
            servidor.kill()
