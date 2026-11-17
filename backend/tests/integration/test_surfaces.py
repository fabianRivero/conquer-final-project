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


def test_la_pagina_del_cliente_no_polla():
    """The client's page does not poll.

    A poll would multiply the credential's exposure for no benefit.
    """
    codigo = _codigo("src/surfaces/Cliente.tsx")

    assert "setInterval" not in codigo
    assert "setTimeout" not in codigo


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


def test_el_credential_del_cliente_no_se_guarda():
    """The credential lives in React state and nowhere else.

    It is not in `localStorage`, not in `sessionStorage`, not in the URL.
    """
    codigo = _codigo("src/surfaces/Cliente.tsx")

    for prohibido in ("localStorage", "sessionStorage", "document.cookie"):
        assert prohibido not in codigo, (
            f"el cliente guarda el credential en {prohibido}"
        )


def test_el_campo_del_credential_no_se_autocompleta():
    """The credential field carries `autocomplete="off"`.

    The browser's password manager would otherwise keep the credential
    where the page cannot reach it - and where a leak could.
    """
    codigo = _codigo("src/components/Acceso.tsx")

    assert 'autoComplete="off"' in codigo
    assert "type=\"password\"" in codigo


def test_el_cliente_limpia_el_credential_al_navegar():
    """The credential is cleared on navigation."""
    codigo = _codigo("src/surfaces/Cliente.tsx")

    # The unmount clears it.
    assert "setCodigo(null)" in codigo


def test_la_propuesta_del_cliente_no_lleva_cargo_id():
    """The proposal names NO charge.

    The body carries an `importe` and a `referencia`, and nothing else:
    the FIFO decides which charges the payment retires, and a body that
    carries a `cargo_id` is refused with `campo_no_admitido` (ADR-27).
    """
    codigo = _codigo("src/surfaces/Cliente.tsx")
    componente = _codigo("src/components/ProponerPago.tsx")

    assert "cargo_id" not in codigo
    assert "cargo_id" not in componente
    # And the body it sends carries the importe and the referencia.
    assert "importe" in componente
    assert "referencia" in componente


def test_el_cliente_dice_que_el_dueno_registra_el_pago():
    """The component says plainly that the owner still records the payment.

    A client that believed its payment was recorded would be a client
    that believes it still owes the money.
    """
    componente = _codigo("src/components/ProponerPago.tsx")

    assert "dueno" in componente


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
        "Credenciales.tsx",
        "PropuestaForm.tsx",
        "PagosPropuestos.tsx",
        "Pantalla.tsx",
        "Acceso.tsx",
        "Estado.tsx",
        "ProponerPago.tsx",
    ],
)
def test_el_componente_existe(componente):
    """The eleven components of the three surfaces."""
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
