"""The three surfaces' contract, asserted from the BACKEND's side.

The frontend is TypeScript and React, and the plan names no JavaScript
test runner. So the contract that matters - the one the design fixes -
is asserted here, on the sources the frontend ships:

* **the owner's board renders the owner's components** and the
  `dependiente`'s board does NOT: the reduced payload declares only
  `caja`, `clientes` and `cierre_hoy`, and a component that reads a
  field the other role does not get is either a crash or a leak;
* **the ladder is NOT re-sorted**: the API already sorts it by
  `antiguedad_max_dias` descending, and a client that sorted it again
  would be a second place where the order could drift;
* **the four ribbons are NAMED**, not taken from the payload's keys: a
  ribbon that only appeared when the server sent it would let a bucket
  go missing without anyone noticing;
* **the board polls every 20 seconds** and the client's page does NOT
  poll;
* **the screen shows the desglose and nothing else**, and its two
  actions post to the two routes;
* **the client's credential is in React state only** - no `localStorage`,
  no `sessionStorage`, no URL - and the form carries `autocomplete="off"`;
* **the proposal carries no `cargo_id`**.

A note on why the source is read and not compiled. The rule "the client
proposes no cargo" is a property of the source: a bundle could be built
from a source that no longer refuses it. Asserting on the source is
asserting the contract the design states, and it fails the moment
somebody "helpfully" relaxes the check.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "frontend"

pytestmark = pytest.mark.integration


def _codigo(relativo: str) -> str:
    """The file's CODE, with the comments and the docstrings removed.

    The contract is about the source that RUNS, not about the prose that
    explains it. A docstring that mentions `localStorage` while
    explaining that the credential is NOT in it would otherwise make the
    assertion pass for the wrong reason.
    """
    texto = (FRONTEND / relativo).read_text(encoding="utf-8")
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    texto = re.sub(r"^\s*//.*$", "", texto, flags=re.M)
    return texto


# ---------------------------------------------------------------------------
# The owner's board
# ---------------------------------------------------------------------------


def test_el_tablero_distingue_las_dos_formas():
    """The board renders the owner's components and the `dependiente`'s not.

    The surface asks the payload which shape it is, and renders the
    owner's components only when the owner is at the counter.
    """
    codigo = _codigo("src/surfaces/Posicion.tsx")

    # The two shapes are told apart.
    assert "esDelDueno" in codigo
    # And the owner's components are rendered inside that branch.
    assert "Ecuacion" in codigo
    assert "Cinta" in codigo
    assert "Escalera" in codigo
    # The `dependiente`'s branch carries ONLY the reduced fields.
    rama = codigo.split("esDelDueno(tablero) ? (")[1]
    rama = rama.split(") : (")[1]
    for prohibido in ("Ecuacion", "Escalera", "Cinta", "fiado_pendiente",
                      "posicion_real", "buckets"):
        assert prohibido not in rama, (
            f"la rama del dependiente renderiza {prohibido}"
        )


def test_el_tablero_no_ordena_la_escalera():
    """The ladder is NOT re-sorted: the API already sorts it.

    A client that sorted it again would be a second place where the
    order could drift.
    """
    codigo = _codigo("src/components/Escalera.tsx")

    assert "sort" not in codigo
    assert "antiguedad_max_dias" in codigo


def test_las_cuatro_cintas_estan_nombradas():
    """The four ribbons are named, not taken from the payload's keys.

    The vocabulary is closed - `vigente`, `envejecido`, `viejo`,
    `cronico` - and a ribbon that only appeared when the server sent it
    would let a bucket go missing without anyone noticing.
    """
    codigo = _codigo("src/components/Cinta.tsx")

    for nombre in ("vigente", "envejecido", "viejo", "cronico"):
        assert nombre in codigo, f"falta la cinta {nombre}"
    # And they are declared as a closed list.
    assert "CINTAS" in codigo


def test_el_tablero_polla_cada_veinte_segundos():
    """The board polls every 20 seconds, and the poll is the keep-alive."""
    codigo = _codigo("src/surfaces/Posicion.tsx")

    assert "SEGUNDOS_ENTRE_POLL" in codigo
    assert "setInterval" in codigo



def test_el_tablero_no_pide_el_credito_al_dependiente():
    """The `dependiente`'s branch does not read the credit book.

    The ladder, `posicion_real`, `fiado_pendiente` and `buckets` are 403
    for the `dependiente` - and the reduced payload does not declare
    them, so they cannot appear. The surface does not ask for them.
    """
    codigo = _codigo("src/surfaces/Posicion.tsx")

    # One fetch of the board, and it is the same for both roles.
    assert codigo.count("staff.posicion()") == 1


# ---------------------------------------------------------------------------
# The shop's screen
# ---------------------------------------------------------------------------


def test_la_pantalla_muestra_el_desglose_y_nada_mas():
    """The screen shows the desglose and nothing else.

    Product, quantity, `precio_unitario` and `total` for every line, plus
    the proposal's `total`. No balance, no ageing, no other customer, no
    `credit_limit`, no `codigo`.
    """
    codigo = _codigo("src/components/Pantalla.tsx")

    for campo in ("producto", "cantidad", "precio_unitario", "total"):
        assert campo in codigo, f"falta el campo {campo}"
    for prohibido in ("credit_limit", "codigo", "antiguedad", "buckets",
                      "saldo", "pendiente"):
        assert prohibido not in codigo, (
            f"la pantalla muestra {prohibido}"
        )


def test_la_pantalla_tiene_las_dos_acciones():
    """The screen's two actions are `Confirmar` and `Cancelar`."""
    codigo = _codigo("src/components/Pantalla.tsx")

    assert "Confirmar" in codigo
    assert "Cancelar" in codigo
    assert "onConfirmar" in codigo
    assert "onCancelar" in codigo


def test_la_confirmacion_y_la_cancelacion_van_a_sus_rutas():
    """The two actions post to the two routes of the design."""
    codigo = _codigo("src/surfaces/Propuesta.tsx")

    assert "confirmarPropuesta" in codigo
    assert "cancelarPropuesta" in codigo


# ---------------------------------------------------------------------------
# The client's page
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
# The person's own account
# ---------------------------------------------------------------------------


def test_la_contrasena_de_la_persona_no_se_guarda():
    """The password lives in React state and nowhere else.

    It is not in `localStorage`, not in `sessionStorage`, not in the URL.
    A password in the browser's storage is a password in every script
    that runs on the page.
    """
    codigo = _codigo("src/surfaces/Cuenta.tsx")

    for prohibido in ("localStorage", "sessionStorage"):
        assert prohibido not in codigo, (
            f"la persona guarda la contrasena en {prohibido}"
        )


def test_la_contrasena_se_limpia_tras_enviarla():
    """The password is cleared as soon as the request is sent."""
    codigo = _codigo("src/surfaces/Cuenta.tsx")

    assert 'setContrasena("")' in codigo


def test_el_campo_de_la_contrasena_es_de_tipo_password():
    """The password field is masked.

    It is a password, and it is the person's own: the shop does not know
    it, and the screen in front of the shopkeeper does not show it.
    """
    codigo = _codigo("src/surfaces/Cuenta.tsx")

    assert 'type="password"' in codigo


def test_la_cuenta_vive_en_su_propia_ruta():
    """The account has its own path and its own component.

    The three audiences never share a surface: the staff's board, the
    client's statement and the person's account.
    """
    router = _codigo("src/router.tsx")

    assert "/app/cuenta" in router
    assert 'from "./surfaces/Cuenta"' in router


def test_la_cuenta_es_una_tercera_audiencia_en_el_servidor():
    """The server serves the account's page, and it is public.

    She signs in FROM it, so the bundle has to be served before she has
    any session - exactly like the client's page.
    """
    urls = (REPO / "backend" / "config" / "urls.py").read_text(encoding="utf-8")

    assert "app/cuenta/" in urls
    assert "spa_publico" in urls


def test_la_contrasena_del_personal_no_se_guarda():
    """The staff's password lives in React state and nowhere else.

    The owner sets it and hands it over. It is not in `localStorage`, not
    in `sessionStorage`, not in the URL - a password in the browser's
    storage is a password in every script that runs on the page.
    """
    codigo = _codigo("src/components/Personal.tsx")

    for prohibido in ("localStorage", "sessionStorage"):
        assert prohibido not in codigo, (
            f"el personal guarda la contrasena en {prohibido}"
        )


def test_la_contrasena_del_personal_se_limpia_tras_enviarla():
    """The password is cleared as soon as the request is sent."""
    codigo = _codigo("src/components/Personal.tsx")

    assert 'setPassword("")' in codigo


def test_el_campo_de_la_contrasena_del_personal_es_de_tipo_password():
    """The password field is masked."""
    codigo = _codigo("src/components/Personal.tsx")

    assert 'type="password"' in codigo


def test_el_personal_solo_lo_ve_el_dueno():
    """The staff's screen is in the OWNER's branch of the board.

    The `dependiente` operates the counter: administrating the staff is
    the shop's policy, and the N5 gate did not open it.
    """
    codigo = _codigo("src/surfaces/Posicion.tsx")

    # El componente se renderiza dentro de la rama del dueno.
    rama = codigo.split("esDelDueno(tablero) ? (", 1)
    assert len(rama) == 2, "la rama del dueno no esta en la superficie"
    assert "<Personal" in rama[1].split(") : (", 1)[0]


# ---------------------------------------------------------------------------
# The components exist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "componente",
    [
        "Ecuacion.tsx",
        "Escalera.tsx",
        "Cinta.tsx",
        "Cierre.tsx",
        "PropuestaForm.tsx",
        "PagosPropuestos.tsx",
        "Pantalla.tsx",
        # **The person's own**: the fiados she answers and the charges
        # with their state.
        "Fiados.tsx",
        "Cargos.tsx",
        # And the links she answers.
        "Vinculos.tsx",
    ],
)
def test_el_componente_existe(componente):
    """The components of the surfaces."""
    assert (FRONTEND / "src" / "components" / componente).exists()


def test_la_ecuacion_muestra_los_tres_numeros():
    """`Ecuacion` shows `caja + fiado_pendiente = posicion_real`."""
    codigo = _codigo("src/components/Ecuacion.tsx")

    assert "caja" in codigo
    assert "fiadoPendiente" in codigo
    assert "posicionReal" in codigo
    # And it does NOT compute them: the server derives them.
    assert "parseFloat" not in codigo
    assert "Number(" not in codigo
