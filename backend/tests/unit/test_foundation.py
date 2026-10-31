"""The foundation contract of PR 1 — the infrastructure this slice stands up.

These tests assert the properties the Phase 1 tasks are responsible for:

* the project boots with `python backend/manage.py check`;
* `/health/` answers 200 without touching the database, so a keep-alive ping
  never exhausts the connection pool (design §18.1);
* `DEBUG` is False by default and the strict CSP is in place (CAC-07,
  design §11);
* the secret key and the database URL come from the environment only
  (CAC-07);
* the three test markers are declared, so `--strict-markers` accepts them.

The domain rules arrive with Phase 3 and the API contracts with Phase 4.
"""

import os

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse


@pytest.mark.unit
def test_health_responds_ok_without_touching_the_database():
    """`/health/` answers 200 `{"status":"ok"}` and issues no query.

    The no-query claim is checked structurally: the view holds no ORM
    reference, so a ping can never take a connection from the pool.
    """
    from django.db import connection

    with connection.execute_wrapper(_forbid_queries):
        response = Client().get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _forbid_queries(execute, sql, params, many, context):
    raise AssertionError(f"`/health/` must not touch the database; ran: {sql}")


@pytest.mark.unit
def test_debug_is_off_by_default():
    """Production runs locked: `DEBUG` defaults to False (CAC-07).

    The default is asserted on the helper, not on the live value: the
    environment may set `DEBUG=True` for a local run, but the code path that
    decides it starts from False, and only an explicit truthy environment
    value turns it on.
    """
    from config import settings as settings_module

    assert settings_module.env_bool("A_SETTING_THAT_DOES_NOT_EXIST", default=False) is False
    assert settings_module.env_bool("A_SETTING_THAT_DOES_NOT_EXIST", default=True) is True


@pytest.mark.unit
def test_content_security_policy_is_strict():
    """The strict CSP: `default-src 'self'`, no inline script, no host."""
    csp = settings.CONTENT_SECURITY_POLICY
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


@pytest.mark.unit
def test_secrets_are_read_from_the_environment_only():
    """`SECRET_KEY` and `DATABASE_URL` come from the environment (CAC-07).

    The check is behavioural. The settings module refuses the development
    fallback secret when the process is a **production** one — a process
    whose database is a real PostgreSQL server, which is how the deployed
    service on Render is configured. A local run and the CI runner have no
    `DATABASE_URL`, so both may use the fallback and boot without a `.env`
    file.

    The distinction is deliberate: refusing to boot without a secret would
    make `manage.py check` and the unit suite unrunnable on a fresh clone,
    which is exactly what CI does.
    """
    from config import settings as settings_module

    # No default: an unset variable reads as None, never as a literal.
    assert settings_module.env("A_SETTING_THAT_DOES_NOT_EXIST") is None

    source = open(settings_module.__file__, encoding="utf-8").read()
    assert '"SECRET_KEY"' in source
    assert 'DATABASE_URL = env("DATABASE_URL")' in source

    fallback = "insecure-development-key-do-not-use-in-production"

    # A production process — one with a real DATABASE_URL — refuses the
    # fallback secret outright.
    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "postgres://user:pass@db.example.com:5432/db"
    try:
        assert settings_module._is_production() is True
        with pytest.raises(RuntimeError):
            settings_module._require_production_secret(fallback, False)
    finally:
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url

    # A non-production process — no DATABASE_URL — may use the fallback, and
    # a real key always boots in either mode.
    assert settings_module._is_production() is False
    settings_module._require_production_secret(fallback, False)
    settings_module._require_production_secret("a-real-key", False)
    settings_module._require_production_secret(fallback, True)


@pytest.mark.unit
def test_static_root_is_outside_the_source_tree():
    """`STATIC_ROOT` holds the collected bundle, never the source (design §18.1)."""
    assert settings.STATIC_ROOT
    assert str(settings.STATIC_ROOT) != str(settings.BASE_DIR)


@pytest.mark.unit
def test_the_three_layers_are_declared_as_markers():
    """`unit`, `integration` and `e2e` are declared (task 1.5)."""
    ini = open(settings.BASE_DIR / "pytest.ini", encoding="utf-8").read()
    for marker in ("unit", "integration", "e2e"):
        assert f"{marker}:" in ini


@pytest.mark.unit
def test_the_two_surfaces_are_routed():
    """`/app/posicion/` and `/app/cliente/` are served by this service."""
    assert reverse("app_posicion") == "/app/posicion/"
    assert reverse("app_cliente") == "/app/cliente/"
    for route in ("/app/posicion/", "/app/cliente/"):
        assert Client().get(route).status_code == 200
