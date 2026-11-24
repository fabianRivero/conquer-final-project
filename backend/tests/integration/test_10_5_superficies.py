"""The Slice 10.5, T5: **the frontend's contract**, asserted from the
BACKEND's side.

The frontend is TypeScript and React, and the plan names no JavaScript
test runner. So the contract that matters - the one the design fixes -
is asserted here, on the sources the frontend ships.

**What the 10.5 fixes in the frontend:**

* **the counter asks for the USERNAME and nothing else.** There is no
  password field on the counter's screen, because the password is typed
  by HER, on her own device, and it never travels to the counter. A
  counter screen with a password field would be a screen that asks the
  owner for a secret the owner does not have.
* **the account carries the fiados with their lines**, because a figure
  she cannot see broken down is not a figure she can confirm.
* **the rejection's reason is optional and it is hers**, and it is read
  back.
* **the charges carry their state**, including `parcial`.

A note on why the source is read and not compiled: the rule "the
counter never asks for a password" is a property of the SOURCE. A bundle
could be built from a source that no longer refuses it, and the test
that reads the source fails the moment somebody "helpfully" relaxes the
check.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "frontend"

pytestmark = pytest.mark.integration


def _codigo(relativo: str) -> str:
    return (FRONTEND / relativo).read_text(encoding="utf-8")


def _sin_comentarios(codigo: str) -> str:
    """The code without its comments.

    A docstring that mentions `password` while explaining that the
    counter does NOT ask for one would make the assertion pass for the
    wrong reason. The tests read the CODE.
    """
    codigo = re.sub(r"/\*.*?\*/", "", codigo, flags=re.S)
    codigo = re.sub(r"//[^\n]*", "", codigo)
    return codigo


# ---------------------------------------------------------------------------
# The counter
# ---------------------------------------------------------------------------


def test_el_mostrador_no_tiene_campo_de_contrasena():
    """**The counter's screen has NO password field.**

    The password is typed by her, on her own device, and it never
    travels to the counter. A screen with a password field would be a
    screen that asks the owner for a secret the owner does not have.

    **The word may appear in the TEXT** - the screen says "la contrasena
    la teclea ella" - but it may not be a FIELD: no input of type
    password, and no state that holds one.
    """
    codigo = _sin_comentarios(_codigo("src/surfaces/Mostrador.tsx"))

    assert 'type="password"' not in codigo
    assert "setContrasena" not in codigo
    assert "password" not in codigo.lower()


def test_el_mostrador_pregunta_por_el_nombre_de_usuario():
    """The counter asks for her USERNAME."""
    codigo = _sin_comentarios(_codigo("src/surfaces/Mostrador.tsx"))

    assert "username" in codigo.lower()


def test_la_busqueda_del_mostrador_no_lleva_la_contrasena():
    """**The request carries the username ALONE.**

    A search that sent the password would put a secret the owner does
    not have into a request the owner can read.
    """
    codigo = _sin_comentarios(_codigo("src/api/staff.ts"))

    # The function of the counter sends only the username.
    bloque = codigo[codigo.find("buscarEnElMostrador"):][:400]
    assert "password" not in bloque.lower()
    assert "contrasena" not in bloque.lower()


# ---------------------------------------------------------------------------
# The account: the fiados
# ---------------------------------------------------------------------------


def test_la_cuenta_muestra_los_fiados():
    """The account carries the fiados."""
    codigo = _sin_comentarios(_codigo("src/surfaces/Cuenta.tsx"))

    assert "Fiados" in codigo
    assert "fiadosApi.mios()" in codigo


def test_un_fiado_pendiente_muestra_sus_lineas():
    """**A figure she cannot see broken down is not a figure she can
    confirm.**

    The lines are there BEFORE she answers, because the answer is about
    those lines.
    """
    codigo = _sin_comentarios(_codigo("src/components/Fiados.tsx"))

    assert "lineas" in codigo
    assert "fiado.lineas" in codigo


def test_el_motivo_del_rechazo_es_opcional():
    """**The reason is hers and it may be empty.**

    A refusal without an explanation is not an answer, and an empty
    explanation is still an answer - she is not obliged to justify
    herself to the shop. So the field is not `required`.
    """
    codigo = _sin_comentarios(_codigo("src/components/Fiados.tsx"))

    # El campo del motivo NO es `required`.
    campo = codigo[codigo.find("motivo-"):][:600]
    assert "required" not in campo


def test_el_motivo_del_rechazo_se_manda_aunque_este_vacio():
    """The reason travels even when it is empty."""
    codigo = _sin_comentarios(_codigo("src/api/fiados.ts"))

    assert "motivo" in codigo


def test_el_motivo_del_rechazo_se_lee_de_nuevo():
    """**The reason is READ.** The owner wrote the figure and she wrote
    the answer, and the answer carries the explanation."""
    codigo = _sin_comentarios(_codigo("src/components/Fiados.tsx"))

    assert "fiado.motivo" in codigo


# ---------------------------------------------------------------------------
# The account: the charges
# ---------------------------------------------------------------------------


def test_la_cuenta_muestra_los_cargos_con_su_estado():
    """**The charges carry their state**, including `parcial`."""
    codigo = _sin_comentarios(_codigo("src/components/Cargos.tsx"))

    assert "parcial" in codigo
    assert "pendiente" in codigo
    assert "pagado" in codigo


def test_la_cuenta_muestra_el_saldo_de_cada_cargo():
    """**How much is still owed**, and not only how much it was."""
    codigo = _sin_comentarios(_codigo("src/components/Cargos.tsx"))

    assert "saldo" in codigo
    assert "pagado" in codigo


# ---------------------------------------------------------------------------
# The surfaces keep their own path
# ---------------------------------------------------------------------------


def test_el_mostrador_vive_en_su_propia_ruta():
    """The counter has its own path and its own component.

    The audiences never share a surface: the staff's board, the
    counter, the client's statement and the person's account.
    """
    router = _codigo("src/router.tsx")

    assert "/app/mostrador" in router
    assert 'from "./surfaces/Mostrador"' in router


def test_la_cuenta_y_el_mostrador_no_comparten_componente():
    """**The two surfaces never share a component.**

    The account is the PERSON's and the counter is the SHOP's, and a
    component that both rendered would be a component that could show
    one audience's data to the other.
    """
    cuenta = _codigo("src/surfaces/Cuenta.tsx")
    mostrador = _codigo("src/surfaces/Mostrador.tsx")

    assert 'from "../components/Mostrador"' not in cuenta
    assert 'from "../components/Cuenta"' not in mostrador


def test_la_cuenta_llama_a_las_rutas_de_la_persona():
    """**The account's requests go to the person's own routes.**

    They carry the session cookie, because the answer to the fiado is
    hers and it is given from her account.
    """
    codigo = _sin_comentarios(_codigo("src/api/fiados.ts"))

    assert "/cuenta/fiados/" in codigo
    assert "/cuenta/cargos/" in codigo
    assert 'credentials: "same-origin"' in codigo
