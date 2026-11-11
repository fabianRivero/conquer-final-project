"""The ORM-free guarantee of the domain layer (CP-06, PA-11, IC-06 — ADR-3).

`backend/tienda/domain/` must import **no Django, no DRF and no app
module**. This is not a convention anyone has to remember: this test
AST-parses **every** file of the package and fails on a forbidden import.

The check is an AST walk, not a text search, so it sees what the interpreter
sees:

* `import django.db` and `from django.db import connection` are both caught;
* `from django.db import models` under any alias is caught;
* `import tienda.domain.types` — the package importing **itself** by
  absolute name — is caught, because an absolute import of `tienda` is an
  import of an app module;
* a **relative** import of a sibling (`from .types import Bucket`) is
  allowed, and so is importing a sibling module directly by name.

The package may import from the **standard library only**, plus its own
sibling modules. Nothing else.

This test reads the files; it never imports them. That is deliberate: the
whole point of the guarantee is that the domain layer can be exercised with
no Django settings configured and no database at all.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# The package under inspection.
DOMAIN_DIR = Path(__file__).resolve().parents[2] / "tienda" / "domain"

# The prefixes that may never be imported from inside the package.
FORBIDDEN_PREFIXES = ("django", "rest_framework", "tienda")

# The modules of the standard library the package is allowed to use. The
# check is by *root module name*, so `decimal.Decimal` and `datetime` are
# allowed while `django.db` is not.
ALLOWED_STDLIB = frozenset(
    {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "itertools",
        "math",
        "numbers",
        "operator",
        "re",
        "typing",
    }
)


def _domain_files() -> list[Path]:
    """Every Python file of the domain package."""
    assert DOMAIN_DIR.is_dir(), f"the domain package is missing: {DOMAIN_DIR}"
    return sorted(DOMAIN_DIR.rglob("*.py"))


def _imported_roots(tree: ast.AST) -> list[tuple[str, int]]:
    """The root module of every import in the tree, with its line number.

    Both import forms are read:

    * `import a.b.c` → the root `a`;
    * `from a.b import c` → the root `a`.

    A relative import (`from .types import X`) has no root module — the
    `level` attribute is greater than zero — and is therefore not reported.
    """
    roots: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.append((alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # A relative import: a sibling of the package. Allowed.
                continue
            if node.module:
                roots.append((node.module.split(".")[0], node.lineno))
    return roots


@pytest.mark.unit
def test_the_domain_package_exists():
    """The package is there — without it the guarantee would be vacuous.

    An empty package would pass every check below, so this test asserts
    that the package actually holds the modules of design §10.
    """
    files = _domain_files()
    names = {f.name for f in files}
    for esperado in (
        "__init__.py",
        "types.py",
        "position.py",
        "allocation.py",
        "ageing.py",
        "evaluation.py",
        "charges.py",
        "confirmation.py",
        "stock.py",
        "cash.py",
    ):
        assert esperado in names, f"the domain package has no {esperado}"


@pytest.mark.unit
def test_no_module_of_the_package_imports_django_or_drf():
    """No file of the package imports Django, DRF or an app module (ADR-3)."""
    offenders: list[str] = []
    for path in _domain_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for root, line in _imported_roots(tree):
            if root in FORBIDDEN_PREFIXES:
                offenders.append(f"{path.name}:{line} imports {root!r}")

    assert offenders == [], (
        "the domain layer must import no Django, no DRF and no app module:\n"
        + "\n".join(offenders)
    )


@pytest.mark.unit
def test_the_package_imports_only_the_standard_library():
    """Every import of the package is a standard-library module.

    The allowance for the standard library is an explicit list, so a new
    third-party dependency cannot slip into the domain layer unnoticed: it
    would have to be added here deliberately.
    """
    offenders: list[str] = []
    for path in _domain_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for root, line in _imported_roots(tree):
            if root in FORBIDDEN_PREFIXES:
                continue
            if root not in ALLOWED_STDLIB:
                offenders.append(f"{path.name}:{line} imports {root!r}")

    assert offenders == [], (
        "the domain layer may import the standard library only:\n"
        + "\n".join(offenders)
    )


@pytest.mark.unit
def test_the_package_never_imports_itself_by_absolute_name():
    """`import tienda.domain.types` is forbidden — a relative import is not.

    The rule is stronger than "no app module": the package may not import
    `tienda` **at all**, not even its own subpackage. An absolute
    `tienda.domain.types` would pull the `tienda` package — and with it
    Django's app registry — into a layer that must stay free of it.
    """
    offenders: list[str] = []
    for path in _domain_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for root, line in _imported_roots(tree):
            if root == "tienda":
                offenders.append(f"{path.name}:{line} imports {root!r}")

    assert offenders == [], (
        "the domain layer must not import `tienda`; use a relative import:\n"
        + "\n".join(offenders)
    )


@pytest.mark.unit
def test_a_relative_import_is_read_as_allowed():
    """The check itself works: a relative sibling import is not a violation.

    A guard that cannot tell an allowed import from a forbidden one proves
    nothing. This test parses a snippet that uses the allowed form and
    asserts the walker reports nothing for it.
    """
    arbol = ast.parse("from .types import Bucket\nfrom . import ageing\n")
    assert _imported_roots(arbol) == []


@pytest.mark.unit
def test_a_forbidden_import_is_read_as_a_violation():
    """The check itself works: a Django import *is* reported.

    The mirror of the previous test. Without it, a broken walker would make
    every other test in this file pass vacuously.
    """
    arbol = ast.parse("import django.db\nfrom django.db.models import Q\n")
    roots = {root for root, _ in _imported_roots(arbol)}
    assert roots == {"django"}


@pytest.mark.unit
def test_no_module_of_the_package_holds_a_django_settings_access():
    """No module reads `django.conf.settings` or similar at import time.

    The AST check above already rejects the import. This one is the second
    half of the same guarantee: it asserts the *text* of the package never
    mentions the forbidden names, which catches a dynamic import that the
    AST walk cannot see — `__import__("django.db")` or an `importlib` call.
    """
    for path in _domain_files():
        source = path.read_text(encoding="utf-8")
        for prohibido in ("django", "rest_framework", "__import__", "importlib"):
            assert prohibido not in source, (
                f"{path.name} mentions {prohibido!r}; the domain layer must "
                "stay free of Django, of DRF and of dynamic imports"
            )


@pytest.mark.unit
def test_no_module_of_the_package_imports_the_models():
    """No file of the package imports `tienda.models`.

    The rule is stronger than "no app module": the package may not import
    `tienda` **at all**, not even its own subpackage. An absolute
    `tienda.domain.types` would pull the `tienda` package — and with it
    Django's app registry — into a layer that must stay free of it.

    This test names the specific module that would break the boundary
    hardest, so the reason is recorded next to the assertion: a rule that
    reaches for the ORM row would be a rule that cannot be exercised
    without a database.
    """
    offenders: list[str] = []
    for path in _domain_files():
        source = path.read_text(encoding="utf-8")
        for linea in source.splitlines():
            stripped = linea.strip()
            if stripped.startswith("#"):
                continue
            if "tienda.models" in stripped or "from tienda import" in stripped:
                offenders.append(f"{path.name}: {stripped}")

    assert offenders == [], (
        "the domain layer must not import the ORM models:\n" + "\n".join(offenders)
    )


@pytest.mark.unit
def test_the_package_names_no_removed_vocabulary():
    """No live code in the package uses the v1 concepts.

    The dispute machinery is gone: the `nota de crédito`, the `en_disputa`
    state, the `importe_reclamado` field and the credit-note parameter of
    `allocate_payments`. A leftover reference would mean a rule that
    computes something the model no longer stores.

    Only **live code** is checked: a mention inside a docstring that
    explains what was removed is a documentation of the change, not a use of
    it. So the check looks at the AST for the names that would be
    referenced at runtime.
    """
    for path in _domain_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            # An attribute access: `EntryKind.NOTA_CREDITO`.
            if isinstance(node, ast.Attribute):
                assert node.attr not in {
                    "NOTA_CREDITO",
                    "EN_DISPUTA",
                }, (
                    f"{path.name}:{node.lineno} uses {node.attr!r}, which the "
                    "v2 model removed"
                )
            # A keyword argument: `allocate_payments(..., credit_notes=...)`.
            if isinstance(node, ast.keyword) and node.arg:
                assert node.arg != "credit_notes", (
                    f"{path.name}:{node.lineno} passes credit_notes=, which the "
                    "v2 model removed"
                )
