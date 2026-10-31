"""The URL map of design §9.1 — one service, one origin.

Three kinds of mount:

* `/health/` — the public liveness probe. It touches **no database**, so a
  keep-alive ping never exhausts the connection pool (design §18.1).
* `/api/v1/…` — the REST API, mounted from `tienda.api.urls` (task 4.21).
* `/app/posicion/` and `/app/cliente/` — the two React surfaces, served from
  the single-page bundle built by Vite in Phase 6 (design §11).
"""

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve as serve_static


def health(request: HttpRequest) -> JsonResponse:
    """The liveness probe. No database access, by contract."""
    return JsonResponse({"status": "ok"})


def spa(request: HttpRequest, view_name: str = "") -> HttpResponse:
    """Serve the single-page bundle for the two `/app/…` routes.

    The bundle is built by Vite into `STATIC_ROOT` (task 6.3). Until that
    build exists, a placeholder keeps the route resolvable instead of 404.
    """
    index = settings.STATIC_ROOT / "index.html"
    if index.exists():
        return serve_static(request, str(index))
    return HttpResponse(
        "<!doctype html>"
        '<html lang="es"><head><meta charset="utf-8">'
        f"<title>{view_name}</title></head>"
        f"<body><div id=\"root\" data-route=\"{view_name}\"></div></body></html>",
        content_type="text/html; charset=utf-8",
    )


def _api_urlpatterns():
    """Build the `/api/v1/…` patterns, tolerating the API's absence.

    `tienda.api.urls` arrives with task 4.21. The import is guarded so the
    project boots and every non-API route keeps working before then; once the
    module exists the mount is picked up with no change here.
    """
    try:
        from tienda.api import urls as tienda_api_urls
    except ImportError:
        return []
    return tienda_api_urls.urlpatterns


urlpatterns = [
    path("health/", health, name="health"),
    path("app/posicion/", lambda request: spa(request, "posicion"), name="app_posicion"),
    path("app/cliente/", lambda request: spa(request, "cliente"), name="app_cliente"),
    # The SPA owns its own sub-paths; anything under `/app/` that is not a
    # surface above falls back to the same bundle.
    re_path(r"^app/(?P<view_name>[a-z\-]+)/$", lambda request, view_name: spa(request, view_name)),
]

# The API mount is appended last so the explicit routes above always win.
urlpatterns += [path("api/v1/", include(_api_urlpatterns()))]
