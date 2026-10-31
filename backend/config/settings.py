"""Django settings for the `fiado-confirmado` backend.

Every secret is read from the environment only (CAC-07): nothing is hard-coded
here and nothing sensitive lives in the repository. The deployment spine is
design §18.1 — Neon PostgreSQL, Render Web Service, WhiteNoise serving the
frontend bundle from the same origin.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# The repository root — `requirements.txt`, `render.yaml` and the `frontend/`
# bundle live one level above `backend/`.
REPO_ROOT = BASE_DIR.parent


def env(name, default=None):
    """Read an environment variable, treating the empty string as unset."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def env_bool(name, default=False):
    """Read a boolean environment variable."""
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=()):
    """Read a comma-separated environment variable as a list of strings."""
    value = env(name)
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

# Production runs locked: DEBUG=False (CAC-07). The default is False, never
# True, so a missing environment variable can never open the debug surface.
DEBUG = env_bool("DEBUG", default=False)

# The secret key comes from the environment only. A deterministic development
# fallback keeps `manage.py check` runnable locally without a `.env` file, and
# it is refused in production by the guard below.
SECRET_KEY = env(
    "SECRET_KEY",
    default="insecure-development-key-do-not-use-in-production",
)


def _require_production_secret(secret_key, debug):
    """Refuse to boot a production instance without a real secret key.

    CAC-07: no secret in the repository — and none missing in production
    either. The development fallback exists only so `manage.py check`, the
    unit suite and a local server run without a `.env` file.

    "Production" is decided by the deployment, not by `DEBUG`: a production
    instance is one whose database is a real PostgreSQL server. A local run
    and the CI runner both have no `DATABASE_URL`, so both may use the
    development fallback. The deployed service on Render always has one, so
    it always needs a real `SECRET_KEY` and refuses the fallback.
    """
    if secret_key.startswith("insecure-development-key") and _is_production():
        raise RuntimeError(
            "SECRET_KEY must be set in the environment for a production "
            "instance (CAC-07: no secret in the repository, none in "
            "production either)."
        )


def _is_production():
    """Whether this process talks to a real PostgreSQL server."""
    return bool(env("DATABASE_URL"))


_require_production_secret(SECRET_KEY, DEBUG)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default=[])

# `ALLOWED_HOSTS` is read from the environment in production (landmine 4: a
# missing value makes every request answer 400). The fallback below keeps a
# local run and the CI runner answerable when the variable is absent; it
# never replaces the environment value when one is set.
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

# `CSRF_TRUSTED_ORIGINS` carries the scheme, comma separated (landmine 4:
# a missing value makes every POST answer 403).
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", default=[])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # The `tienda` application carries the data model of Phase 2.
    "tienda",
]

# ---------------------------------------------------------------------------
# Database — Neon PostgreSQL in production (design §18.1, landmine 1)
# ---------------------------------------------------------------------------

DATABASE_URL = env("DATABASE_URL")

if DATABASE_URL:
    from urllib.parse import unquote, urlparse

    _parsed = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(_parsed.path.lstrip("/")),
            "USER": unquote(_parsed.username or ""),
            "PASSWORD": unquote(_parsed.password or ""),
            "HOST": _parsed.hostname or "",
            "PORT": str(_parsed.port or ""),
            "CONN_MAX_AGE": 60,
            # Neon requires TLS and rejects a plain connection, so `require` is
            # the default for the deployed database. It is an environment
            # setting rather than a constant because the CI service container
            # serves no TLS at all, and a hard-coded `require` makes every
            # connection to it fail with `SSL is required`.
            "OPTIONS": {"sslmode": env("DATABASE_SSLMODE", default="require")},
        }
    }
else:
    # Local development only. The integration suite never runs on SQLite:
    # `select_for_update`, partial unique indexes and CHECK constraint
    # semantics are not exercised there (landmine 7).
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", default=str(REPO_ROOT / "db.sqlite3")),
        }
    }

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Static files — the frontend bundle lands in STATIC_ROOT and is served by
# WhiteNoise on the same origin (design §18.1, CAC-06).
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = Path(env("STATIC_ROOT", default=str(REPO_ROOT / "staticfiles")))
# The frontend bundle is built by Vite straight into STATIC_ROOT (task 6.3),
# so there is no separate source directory to collect from.

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# WhiteNoise serves the collected bundle. It must not answer for a path the
# SPA owns, so the SPA routes are served by Django instead.
WHITENOISE_AUTOREFRESH = DEBUG

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ---------------------------------------------------------------------------
# Authentication and sessions
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/app/login/"
LOGIN_REDIRECT_URL = "/app/posicion/"
LOGOUT_REDIRECT_URL = "/app/login/"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "es-es"
TIME_ZONE = env("TIME_ZONE", default="Europe/Madrid")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Security — CAC-07, landmine 4
# ---------------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# The HTTPS redirect is explicit, not implied by `DEBUG=False`. The platform
# terminates TLS in front of the service and forwards `X-Forwarded-Proto`, so
# the redirect belongs to the deployment configuration, not to the code
# default. Deriving it from `DEBUG` would answer a 301 on every request
# behind a proxy that does not set the header, and would break the
# `/health/` ping that the keep-alive workflow and the Render health check
# both depend on.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The Content-Security-Policy. The frontend bundle is built by Vite in Phase 6
# and served from this same origin, so a strict `default-src 'self'` holds: no
# inline script, no external host, no cross-origin request (CAC-06).
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'"
)

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------


def _exception_handler(exc, context):
    """Route DRF exceptions through the 422 handler of `tienda.api.exceptions`.

    The handler itself belongs to task 4.14 and does not exist yet, so it is
    imported lazily and only at request time. Until it lands, DRF's own
    handler answers — the project boots and stays usable. Once the module
    appears, the 422 vocabulary of design §9.3 takes over with no change here.
    """
    try:
        from tienda.api.exceptions import handler as tienda_handler
    except ImportError:
        from rest_framework.views import exception_handler as default_handler

        return default_handler(exc, context)
    return tienda_handler(exc, context)


REST_FRAMEWORK = {
    # Points at the 422 handler (design §9.3): every validation failure is
    # HTTP 422 with `{"codigo_error": "<code>", "detail": "<message>"}`.
    "EXCEPTION_HANDLER": "config.settings._exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}
