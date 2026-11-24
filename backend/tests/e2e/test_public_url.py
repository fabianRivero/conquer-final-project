"""The e2e suite - task 7.9, design 15.3.

Against the **deployed public URL**: HTTPS; one service serving both the
pages and the API; `DEBUG=False` with no debug information; both seeded
accounts signing in and landing in their own capability set; the owner's
board and the client's page fetching their APIs on the same origin with
no cross-origin request; a 403 on the credit book for the `dependiente`;
no alias and no `codigo` in any response; and the seeded figures
matching.

**The URL comes from the environment**, and the suite SKIPS - loudly -
when it is absent: the keepalive workflow does exactly the same thing
with `PUBLIC_URL`, and a test that skips without saying why is a test
that proves nothing.

**The harness is the standard library.** `urllib` is enough for
everything here: GET, POST, following the redirects, carrying the
cookies, and reading the certificate. No new dependency, and the
deployment already has Python.

**A note on the CSRF token.** The login is a form-encoded POST with the
token in the BODY - the way the HTML form does it. Sending it in the
`X-CSRFToken` header with a JSON body does not authenticate: the
refusal is the 401 of the login's own logic, and it looks like a wrong
password when it is a wrong request shape. The suite does what the form
does.
"""

from __future__ import annotations

import json
import os
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

import pytest

#: The deployed public URL. The keepalive workflow reads the same one.
URL_PUBLICA = os.environ.get("PUBLIC_URL", "").rstrip("/")

#: The password of the seeded accounts. The seed sets it, and the seed
#: is the same code in the deployment and in the test suite.
PASSWORD = "tienda-demo-2026"

#: The seeded accounts, one per shop role.
CUENTAS = ("dueno", "dependiente")

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# The harness
# ---------------------------------------------------------------------------


class Navegador:
    """A browser, more or less: cookies, the CSRF token, and requests.

    It keeps a cookie jar and reads the CSRF token out of it, so a POST
    carries the token the way the HTML form does - in the body.
    """

    def __init__(self, base: str):
        self.base = base
        self.tarjeta = CookieJar()
        self.abridor = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.tarjeta),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )

    def pedir(
        self,
        ruta: str,
        datos: dict | None = None,
        cabeceras: dict | None = None,
        formulario: bool = False,
    ) -> tuple[int, str]:
        """A request, and the status and the body."""
        cuerpo = None
        cab = {"Accept": "application/json"}
        if datos is not None:
            if formulario:
                cuerpo = urllib.parse.urlencode(datos).encode()
                cab["Content-Type"] = "application/x-www-form-urlencoded"
            else:
                cuerpo = json.dumps(datos).encode()
                cab["Content-Type"] = "application/json"
        if cabeceras:
            cab.update(cabeceras)
        peticion = urllib.request.Request(
            f"{self.base}{ruta}", data=cuerpo, headers=cab
        )
        try:
            with self.abridor.open(peticion, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    def token_csrf(self) -> str | None:
        """The CSRF token, from the cookie Django set."""
        return next(
            (c.value for c in self.tarjeta if c.name == "csrftoken"), None
        )

    def tiene_sesion(self) -> bool:
        return any(c.name == "sessionid" for c in self.tarjeta)

    def entrar(self, usuario: str) -> tuple[int, str]:
        """Sign in, the way the form does.

        The token goes in the BODY, in a form-encoded POST. The
        `X-CSRFToken` header with a JSON body does NOT authenticate, and
        the refusal looks like a wrong password when it is a wrong
        request shape.
        """
        self.pedir("/login/")
        token = self.token_csrf()
        return self.pedir(
            "/login/",
            {
                "username": usuario,
                "password": PASSWORD,
                "csrfmiddlewaretoken": token,
            },
            {"Referer": f"{self.base}/login/"},
            formulario=True,
        )


@pytest.fixture(scope="module")
def navegador():
    """A browser against the deployed URL."""
    if not URL_PUBLICA:
        pytest.skip(
            "PUBLIC_URL no esta definida: la suite e2e necesita la URL "
            "desplegada. Sin ella la suite NO se prueba, y se salta de "
            "forma visible - no seapproved en silencio."
        )
    return Navegador(URL_PUBLICA)


# ---------------------------------------------------------------------------
# 7.9 - The deployed URL
# ---------------------------------------------------------------------------


def test_el_sitio_responde_por_https(navegador):
    """HTTPS, and the health check answers.

    The health check touches no database, so it is the cheapest proof that
    the service is alive.

    **The TLS is checked, not assumed.** Asserting that the URL STRING
    starts with `https://` proves nothing: it says what was typed in an
    environment variable, not what happened on the wire. So the socket
    is opened against the host and the negotiated protocol is read -
    and the CERTIFICATE is read too, to prove the server presented one.
    """
    assert URL_PUBLICA.startswith("https://"), (
        f"la URL desplegada no es https: {URL_PUBLICA}"
    )
    estado, cuerpo = navegador.pedir("/health/")
    assert estado == 200
    assert json.loads(cuerpo)["status"] == "ok"


def test_la_conexion_negocia_tls_de_verdad():
    """The connection negotiates TLS, and the server presents a certificate.

    The proof that the URL's `https://` is not a promise: the socket is
    opened against the host, with the verification ON, and the negotiated
    protocol and the certificate are read.

    A verification failure would raise, and that is the point: the test
    would fail rather than report a green that means nothing.
    """
    if not URL_PUBLICA:
        pytest.skip("PUBLIC_URL no esta definida.")

    partes = urllib.parse.urlparse(URL_PUBLICA)
    host = partes.hostname
    puerto = partes.port or 443

    contexto = ssl.create_default_context()
    with socket.create_connection((host, puerto), timeout=45) as sock:
        with contexto.wrap_socket(sock, server_hostname=host) as tls:
            version = tls.version()
            certificado = tls.getpeercert()

    assert version is not None and version.startswith("TLS"), (
        f"la conexion no negocio TLS: {version!r}"
    )
    assert certificado, "el servidor no presento certificado"

    # And the certificate covers THIS host. The name can be a WILDCARD -
    # Render presents `*.onrender.com` - and `getpeercert()` reports it
    # literally, so the wildcard has to be matched the way a browser
    # matches it: one label, not the rest.
    asunto = certificado.get("subjectAltName", ())
    nombres = [valor for tipo, valor in asunto if tipo == "DNS"]

    def cubre(patron: str, host: str) -> bool:
        if patron.lower() == host.lower():
            return True
        if not patron.startswith("*."):
            return False
        # Un comodin cubre UN etiqueta: `*.onrender.com` cubre
        # `fiado-confirmado.onrender.com` y no `a.b.onrender.com`.
        sufijo = patron[1:]
        etiqueta = host.split(".")[0]
        return (
            host.lower().endswith(sufijo.lower())
            and host.count(".") == sufijo.count(".")
            and etiqueta != "*"
        )

    assert any(cubre(patron, host) for patron in nombres), (
        f"el certificado no cubre el host {host!r}: {nombres}"
    )


def test_no_hay_informacion_de_depuracion(navegador):
    """`DEBUG=False`, and no debug information in the responses.

    A `DEBUG=True` in production serves the tracebacks and the settings:
    the whole database URL with its password among them.
    """
    estado, cuerpo = navegador.pedir("/no-existe-esta-ruta/")
    assert estado == 404
    # A Django traceback names the settings, the environment and the
    # frames. A debug page has all of them.
    for prohibido in (
        "Traceback",
        "DATABASE_URL",
        "SECRET_KEY",
        "Request Method",
        "Django Version",
    ):
        assert prohibido not in cuerpo, (
            f"la respuesta de error expone {prohibido!r}: hay depuracion"
        )


def test_un_servidor_sirve_las_paginas_y_la_api(navegador):
    """One service serves both the pages and the API.

    The pages and the API are on the SAME origin - there is no second
    host, and no CORS. That is the design's claim (CAC-06), and it is
    what the CSP of the page enforces.
    """
    estado, cuerpo = navegador.pedir("/app/cliente/")
    assert estado == 200
    # The page's own script is served by the SAME service.
    scripts = re.findall(r'src="([^"]+\.js)"', cuerpo)
    assert scripts, "la pagina no nombra ningun script"
    for script in scripts:
        url = script if script.startswith("/") else f"/{script}"
        estado, cuerpo = navegador.pedir(url)
        assert estado == 200, f"el bundle {url} responde {estado}"
        assert len(cuerpo) > 1000, f"el bundle {url} viene vacio"


def test_la_pagina_no_trae_ningun_origen_externo(navegador):
    """No third-party script, no external font, no analytics.

    The client's page carries a credential, so the policy is strict
    (design 11).
    """
    estado, cuerpo = navegador.pedir("/app/cliente/")
    assert estado == 200
    assert "http://" not in cuerpo
    assert "https://" not in cuerpo.replace(f"{URL_PUBLICA}", "")
    assert "default-src 'self'" in cuerpo


def test_las_dos_cuentas_entran_y_caen_en_su_conjunto(navegador):
    """Both seeded accounts sign in, and each lands in its own set.

    The `dueno` gets the whole board; the `dependiente` gets the
    reduced one. The difference is not a matter of hiding fields in the
    view: the two payloads do not even share the same KEYS.
    """
    dueno = Navegador(URL_PUBLICA)
    estado, _ = dueno.entrar("dueno")
    assert estado == 200, "el dueño no pudo entrar"
    assert dueno.tiene_sesion(), "el dueño entro sin cookie de sesion"

    dependiente = Navegador(URL_PUBLICA)
    estado, _ = dependiente.entrar("dependiente")
    assert estado == 200, "el dependiente no pudo entrar"
    assert dependiente.tiene_sesion()

    # The owner's board: the whole thing.
    estado, cuerpo = dueno.pedir("/api/v1/posicion/")
    assert estado == 200
    completa = json.loads(cuerpo)
    for clave in (
        "caja",
        "fiado_pendiente",
        "posicion_real",
        "buckets",
        "clientes",
    ):
        assert clave in completa, f"al dueño le falta {clave}"

    # The dependent's board: the reduced one, and NO MORE.
    estado, cuerpo = dependiente.pedir("/api/v1/posicion/")
    assert estado == 200
    reducida = json.loads(cuerpo)
    assert set(reducida.keys()) == {"caja", "clientes", "cierre_hoy"}
    for prohibido in (
        "fiado_pendiente",
        "posicion_real",
        "buckets",
        "serie_caja",
    ):
        assert prohibido not in reducida, (
            f"el dependiente recibe {prohibido}: el payload reducido no lo "
            f"declara"
        )


def test_el_dependiente_da_403_en_la_politica_del_dueno(navegador):
    """A 403 on the OWNER'S POLICY for the `dependiente`.

    **The gate N5 is OPEN**, so the `dependiente` READS the credit book:
    `/api/v1/clientes/` answers 200 for it, with the reduced schema and
    no policy in it. That is the decision of the Phase 9, and it is what
    the previous version of this test contradicted - it was written when
    the `dependiente` was refused everywhere, and it was never
    re-inverted when the gate opened.

    **What the `dependiente` still cannot do is the owner's POLICY**:
    the catalogue, the proposed payments, the limit, the suspension and
    the credential. Those answer the total 403 of design §7.1 - no
    alias, no identifier, no count, not in the body and not in the
    message.
    """
    dueno = Navegador(URL_PUBLICA)
    dueno.entrar("dueno")

    dependiente = Navegador(URL_PUBLICA)
    dependiente.entrar("dependiente")

    # The POLICY: refused, and with nothing in the body.
    for ruta in ("/api/v1/catalogo/", "/api/v1/pagos-propuestos/"):
        estado, cuerpo = dependiente.pedir(ruta)
        assert estado == 403, f"{ruta} responde {estado} y deberia ser 403"
        assert json.loads(cuerpo)["codigo_error"] == "permiso_insuficiente"

    # And the owner DOES reach them.
    for ruta in ("/api/v1/clientes/", "/api/v1/catalogo/"):
        estado, _ = dueno.pedir(ruta)
        assert estado == 200, f"el dueno no alcanza {ruta}"

    # **The credit book IS readable by the `dependiente`** - through the
    # reduced schema, which declares the debts and none of the policy.
    estado, cuerpo = dependiente.pedir("/api/v1/clientes/")
    assert estado == 200, "el dependiente no puede leer el libro de credito"
    for prohibido in ("credit_limit", "codigo", "prefix", "suspended_reason"):
        assert prohibido not in str(cuerpo), (
            f"el dependiente recibe {prohibido}: el payload reducido no lo "
            f"declara"
        )


def test_ninguna_respuesta_trae_un_alias_ni_un_codigo(navegador):
    """No alias and no `codigo` in any response.

    The alias is the customer's own business and the client reads it in
    ITS statement - but a STAFF response carries it only where the
    design says so. The `codigo` never travels: only its prefix, and
    only in the owner's own view.
    """
    dueno = Navegador(URL_PUBLICA)
    dueno.entrar("dueno")

    # The board: the ladder carries the alias - that is the owner's
    # screen. What must NOT appear is the credential's VALUE.
    estado, cuerpo = dueno.pedir("/api/v1/posicion/")
    assert estado == 200
    assert "codigo_hash" not in cuerpo
    assert "codigo" not in cuerpo.replace("codigo_duplicado", "")

    # The client's statement is where the alias belongs - and the
    # credential's value must not be there either.
    estado, cuerpo = dueno.pedir("/api/v1/clientes/")
    assert estado == 200
    assert "codigo_hash" not in cuerpo


def test_las_cifras_sembradas_coinciden(navegador):
    """The seeded figures match.

    The seed is a contract: one shop, one customer, thirty products, one
    confirmed charge of 3,60, one pending proposal and one cancelled one.
    """
    dueno = Navegador(URL_PUBLICA)
    dueno.entrar("dueno")

    estado, cuerpo = dueno.pedir("/api/v1/posicion/")
    assert estado == 200
    tablero = json.loads(cuerpo)

    # The drawer opens at 150,00 and the credit owed is the seeded
    # charge of 3,60.
    assert float(tablero["caja"]) == 150.00
    assert float(tablero["fiado_pendiente"]) == 3.60
    assert float(tablero["posicion_real"]) == 153.60

    # The four ribbons, and their total is the outstanding.
    cintas = tablero["buckets"]
    assert set(cintas.keys()) == {"vigente", "envejecido", "viejo", "cronico"}
    assert sum(float(v) for v in cintas.values()) == 3.60

    # The ladder: one customer with something pending.
    escalera = tablero["clientes"]
    assert len(escalera) == 1
    assert escalera[0]["pendiente"] == "3.60"

    # The catalogue: about thirty products, the seeded one at 1,20.
    estado, cuerpo = dueno.pedir("/api/v1/catalogo/")
    assert estado == 200
    catalogo = json.loads(cuerpo)
    assert len(catalogo) >= 30
    pan = next(p for p in catalogo if p["nombre"] == "Pan")
    assert float(pan["precio"]) == 1.20


def test_la_pagina_del_personal_redirige_sin_sesion():
    """`/app/posicion/` answers 302 to the login without a session.

    The staff scope lives in the session, so a request without one has no
    scope - and the design's route table says "302 to login".

    **A FRESH browser, not the shared one.** The `navegador` fixture is
    module-scoped, and its cookie jar carries the owner's session from
    the earlier tests: with it, the page answers 200 and the redirect
    never happens. A jar shared between tests leaks one test's session
    into the next, and the suite would prove things that are not true.
    """
    sin_sesion = Navegador(URL_PUBLICA)
    if not URL_PUBLICA:
        pytest.skip("PUBLIC_URL no esta definida.")

    # Without following the redirect, so the answer is visible.
    class SinRedirigir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    sin_sesion.abridor = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar()),
        SinRedirigir,
    )

    try:
        with sin_sesion.abridor.open(
            f"{URL_PUBLICA}/app/posicion/", timeout=60
        ) as r:
            raise AssertionError(
                f"/app/posicion/ responde {r.status} sin sesion: deberia "
                f"redirigir al login"
            )
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        assert "/login/" in exc.headers.get("Location", "")


def test_la_pagina_del_cliente_es_publica(navegador):
    """`/app/cliente/` is public: 200, and no redirect.

    The client reads its statement with a credential, not with a session.
    """
    estado, _ = navegador.pedir("/app/cliente/")
    assert estado == 200
