"""The connection's options, built from the DATABASE_URL.

**The query string of the URL reaches the driver.** The connection used
to be built from PARTS, and the URL's own parameters were thrown away:
so `sslmode`, `channel_binding` and `sslrootcert` never arrived, and the
deployment worked by ACCIDENT - the default happened to be the right
one.

Three rules, and they are the contract:

1. **The URL's parameters WIN over `DATABASE_SSLMODE`.** Whoever wrote
   the URL wrote those parameters on purpose, and the URL is the most
   specific statement of intent. The variable stays as the fallback, with
   its default of "require" - Neon demands TLS and the CI's Postgres
   container serves none.
2. **Only the options the driver knows are passed.** Django hands
   `OPTIONS` to `psycopg.connect(**options)`, so an unknown key is a
   TypeError on the FIRST connection - and the query string of a URL can
   carry anything.
3. **`sslrootcert=system` becomes an SSLContext.** The alias is
   libpq's, and libpq looks for a FILE. The system trust store is not a
   file on Windows - it is the OS's own store, reachable only through
   `ssl.create_default_context()`.

**What this test does NOT do.** It does not connect to Neon and it does
not check that a certificate verifies: the machine's trust store is not
the deployment's, and a test that depended on it would pass on the
deployer's laptop and fail on the runner. What it checks is the OPTIONS
that Django would hand to the driver - the contract between the URL and
the connection.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest

pytestmark = pytest.mark.integration

#: The URL of Neon, with the shape the console gives. The password is
#: not a real one: nothing here connects.
URL_NEON = (
    "postgresql://usuario:password@ep-nombre-123.us-east-2.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)


def _ajustes_con(url: str, sslmode: str | None = None):
    """Build the settings with this URL, and return the OPTIONS.

    The settings are a MODULE, and they read the environment at import
    time. So the module is imported with the environment set, and then
    reloaded - and the module is restored afterwards, because the rest of
    the suite needs the settings it had.
    """
    import config.settings as modulo

    previo = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "DATABASE_SSLMODE": os.environ.get("DATABASE_SSLMODE"),
    }
    os.environ["DATABASE_URL"] = url
    if sslmode is None:
        os.environ.pop("DATABASE_SSLMODE", None)
    else:
        os.environ["DATABASE_SSLMODE"] = sslmode

    try:
        importlib.reload(modulo)
        return dict(modulo.DATABASES["default"]["OPTIONS"])
    finally:
        for clave, valor in previo.items():
            if valor is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = valor
        importlib.reload(modulo)


def test_el_sslmode_de_la_url_llega_al_driver():
    """The URL's `sslmode` reaches the driver.

    It used to be thrown away with the rest of the query string.
    """
    opciones = _ajustes_con(
        "postgresql://u:p@host/neondb?sslmode=verify-ca"
    )
    assert opciones["sslmode"] == "verify-ca"


def test_la_variable_es_el_respaldo():
    """Without a query string, the variable decides.

    And its default is "require": Neon demands TLS, and the CI's
    Postgres container serves none - so the CI sets the variable to
    "disable" and the default is only the fallback.
    """
    opciones = _ajustes_con("postgresql://u:p@host/neondb")
    assert opciones["sslmode"] == "require"


def test_la_url_gana_sobre_la_variable():
    """The URL's parameters WIN over the variable.

    Whoever wrote the URL wrote those parameters on purpose.
    """
    opciones = _ajustes_con(
        "postgresql://u:p@host/neondb?sslmode=verify-full",
        sslmode="disable",
    )
    assert opciones["sslmode"] == "verify-full"


def test_el_channel_binding_llega_al_driver():
    """`channel_binding=require` reaches the driver.

    It is the protection against a man in the middle, and it used to be
    dropped with the rest of the query string.
    """
    opciones = _ajustes_con(URL_NEON)
    assert opciones["channel_binding"] == "require"
    assert opciones["sslmode"] == "require"


def test_un_parametro_desconocido_se_descarta():
    """Only the options the driver knows are passed.

    Django hands `OPTIONS` to `psycopg.connect(**options)`, so an
    unknown key is a TypeError on the FIRST connection - and the query
    string of a URL can carry anything.
    """
    opciones = _ajustes_con(
        "postgresql://u:p@host/neondb?sslmode=require&una_opcion_que_no_existe=1"
    )
    assert "una_opcion_que_no_existe" not in opciones
    assert opciones["sslmode"] == "require"


def test_el_almacen_del_sistema_se_convierte_en_un_contexto():
    """`sslrootcert=system` becomes an SSLContext.

    The alias is libpq's, and libpq looks for a FILE: on Windows it
    went looking for `root.crt` in the user's PostgreSQL directory. The
    system trust store is not a file on Windows - it is the OS's own
    store, reachable only through `ssl.create_default_context()`.
    """
    import ssl

    opciones = _ajustes_con(
        "postgresql://u:p@host/neondb?sslmode=verify-full&sslrootcert=system"
    )
    assert "sslrootcert" not in opciones, (
        "el alias 'system' sigue llegando al driver: buscaria un fichero"
    )
    contexto = opciones.get("context")
    assert isinstance(contexto, ssl.SSLContext), (
        "el almacen del sistema no se convirtió en un contexto"
    )
    # The context VERIFIES: that is the whole point of it.
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    # And the hostname is checked too: "verify-full" checks it and
    # "verify-ca" does not.
    assert opciones["sslmode"] == "verify-full"


def test_la_conexion_sin_tls_sigue_siendo_posible():
    """`sslmode=disable` still reaches the driver.

    The CI's Postgres container serves no TLS at all, and a hard-coded
    "require" makes every connection to it fail. The escape hatch has to
    survive.
    """
    opciones = _ajustes_con(
        "postgresql://u:p@host/neondb", sslmode="disable"
    )
    assert opciones["sslmode"] == "disable"
    assert "context" not in opciones
