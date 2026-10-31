"""Shared pytest configuration for the three test layers.

The layers arrive with the phases that fill them: `unit` with the pure domain
rules (Phase 3), `integration` with the model constraints and the API
contracts (Phases 2 and 4), `e2e` with the deployed URL (Phase 6).

A layer that holds no test yet is reported as **one skipped test**, not as a
failed collection. pytest's default for an empty directory is exit code 5
("no tests collected"), which would turn every CI run red while the layer is
still empty. The skip disappears by itself as soon as the layer gains its
first test module, so the accommodation never hides a real failure.

The environment is pinned here so the suite never depends on a shell that
happens to export the right variables. The CI workflow runs
`python -m pytest` with no `.env` file, so the settings module must find a
deterministic development secret and must not redirect to HTTPS behind the
test client. `DEBUG` stays False on purpose: the suite must exercise the
production-shaped configuration, not a relaxed one.
"""

import os
from pathlib import Path

import pytest

# The development fallback secret is allowed here because the test process
# has no `DATABASE_URL`, so the settings module treats it as non-production.
# A deployed instance always has one and still refuses the fallback.
os.environ.setdefault("SECRET_KEY", "insecure-test-key-not-a-real-secret")
os.environ.setdefault("DEBUG", "False")
os.environ.setdefault("SECURE_SSL_REDIRECT", "0")

# The layers that may be empty at any point of the build.
LAYERS = ("unit", "integration", "e2e")


class _EmptyLayerItem(pytest.Item):
    """A single skipped item standing in for a layer that has no test yet."""

    def __init__(self, *, layer, **kw):
        super().__init__(**kw)
        self.layer = layer

    def runtest(self):
        pytest.skip(
            f"The `{self.layer}` layer holds no test yet; "
            "it arrives with a later phase."
        )

    def repr_failure(self, excinfo):
        return excinfo.exconly()

    def reportinfo(self):
        return self.path, 0, f"{self.layer} layer not populated yet"


class _EmptyLayerCollector(pytest.Directory):
    """Collects the single skipped item of an empty layer."""

    def collect(self):
        layer = self.path.name
        yield _EmptyLayerItem.from_parent(
            self, name=f"{layer}_layer_not_populated_yet", layer=layer
        )


def pytest_collect_directory(path: Path, parent):
    """Stand in for a layer directory that holds no test module.

    The hook only fires for the three known layers, and only when the
    directory holds no `test_*.py` module. A layer with tests is collected by
    pytest's own machinery, exactly as before.
    """
    if path.name not in LAYERS:
        return None
    if any(path.glob("test_*.py")):
        return None
    return _EmptyLayerCollector.from_parent(parent, path=path)
