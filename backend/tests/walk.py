"""The leak walk — task 4.1.

The credential is a bearer secret, and a secret that leaks is not a secret
any more. The leak surface of design §5.2 is wide — the staff payloads, the
client payloads, the logs, the URLs, the error bodies, the browser storage
and the clipboard — and this module is the machinery that walks it.

**The walk is over the WHOLE tree.** It visits every key and every value of
a JSON body, recursively, and it looks for a **forbidden token** anywhere.
A check of the top-level keys would miss a credential nested three levels
down, and a credential that reaches a response is a credential that reaches
a log, a cache and a browser's developer console.

The forbidden tokens are the ones that must never cross:

* the **plaintext** of a credential — the only time it exists is the
  issuing response, and that response is the owner's;
* the **`prefix`** — the non-secret head of the credential. It is not
  entropy, but it is half of what an attacker needs to narrow a search,
  and it belongs to the owner alone.

And the staff-only figures — `caja`, `posicion_real`, `credit_limit` and
the rest — must never reach a **client** response. The client is entitled
to its own debt and to nothing else.

**The walk is generic on purpose.** It takes a body and a list of
forbidden tokens, so the same machinery serves the staff tree (R1), the
client tree (R2) and the field-set assertion that carries CAC-10.
"""

from __future__ import annotations

from typing import Any, Iterable

#: The tokens that must never appear in a STAFF response: the credential
#: itself and its prefix.
TOKENS_DE_CREDENCIAL = ("codigo", "prefix")

#: The tokens that must never appear in a CLIENT response: the staff-only
#: figures, plus the credential.
TOKENS_DE_CLIENTE = (
    "caja",
    "fiado_pendiente",
    "posicion_real",
    "buckets",
    "credit_limit",
    "antiguedad_max_dias",
    "suspended_reason",
    "codigo",
    "prefix",
)

#: The tokens that must never appear in ANY response of ANY audience.
TOKENS_DE_AMBOS = ("codigo", "prefix")


def recorrer(body: Any) -> list[tuple[str, Any]]:
    """Every `(path, value)` of a JSON body, recursively.

    The path is the dotted route to the value — `cargos.0.lineas.2.producto`
    — so a report says **where** the leak was, not merely that there was
    one. The list and the dict keys are visited too: a credential hidden in
    a KEY is as leaked as one in a value.
    """
    encontrados: list[tuple[str, Any]] = []
    _recorrer(body, "", encontrados)
    return encontrados


def _recorrer(valor: Any, ruta: str, encontrados: list[tuple[str, Any]]) -> None:
    """The recursive walk itself."""
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            ruta_clave = f"{ruta}.{clave}" if ruta else str(clave)
            encontrados.append((ruta_clave, clave))
            _recorrer(hijo, ruta_clave, encontrados)
    elif isinstance(valor, (list, tuple)):
        for indice, hijo in enumerate(valor):
            ruta_hijo = f"{ruta}.{indice}" if ruta else str(indice)
            encontrados.append((ruta_hijo, hijo))
            _recorrer(hijo, ruta_hijo, encontrados)
    else:
        encontrados.append((ruta, valor))


def buscar(body: Any, tokens: Iterable[str]) -> list[tuple[str, Any]]:
    """Every place a forbidden token appears, by path.

    A token is found in a **value** that contains it as a substring, and in
    a **key** that carries it. The comparison is case-insensitive, because a
    leak does not care about the capitalisation.
    """
    prohibidos = [t.lower() for t in tokens]
    hallazgos: list[tuple[str, Any]] = []

    for ruta, valor in recorrer(body):
        if isinstance(valor, str):
            minuscula = valor.lower()
            for token in prohibidos:
                if token in minuscula:
                    hallazgos.append((ruta, valor))
                    break
        elif isinstance(valor, (int, float)) and not isinstance(valor, bool):
            # A number cannot contain a token, but a credential could be
            # stored as a number by mistake. The check is cheap.
            texto = str(valor).lower()
            for token in prohibidos:
                if len(token) > 3 and token in texto:
                    hallazgos.append((ruta, valor))
                    break

    return hallazgos


def afirmar_sin_fuga(body: Any, tokens: Iterable[str], contexto: str) -> None:
    """Fail if a forbidden token appears anywhere in the body.

    The message names the **path** of every leak, because "there is a leak"
    is not an actionable report: "the credential is at
    `cargos.0.lineas.2.producto`" is.
    """
    hallazgos = buscar(body, tokens)
    if hallazgos:
        rutas = ", ".join(f"{ruta} = {valor!r}" for ruta, valor in hallazgos)
        raise AssertionError(
            f"{contexto}: a forbidden token reached the response at {rutas}. "
            f"The walk covers every key and every value of the tree."
        )


def claves_de(body: Any) -> set:
    """Every key of the tree, by name.

    It is what the CAC-10 assertion reads: the **schema's** declared
    fields, and the fields of a rendered body. A field that is not declared
    cannot be in the response whatever the view hands over.
    """
    nombres = set()
    for _ruta, valor in recorrer(body):
        if isinstance(valor, str):
            nombres.add(valor)
    return nombres
