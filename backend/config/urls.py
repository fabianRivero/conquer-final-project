"""The URL map of design §9.1 — one service, one origin.

Three kinds of mount:

* `/health/` — the public liveness probe. It touches **no database**, so a
  keep-alive ping never exhausts the connection pool (design §18.1).
* `/api/v1/…` — the REST API, mounted from `tienda.api.urls` (task 4.21).
* `/app/posicion/` and `/app/cliente/` — the two React surfaces, served from
  the single-page bundle built by Vite in Phase 6 (design §11).
"""

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import include, path, re_path
from django.views.static import serve as serve_static

import mimetypes

from tienda.views_login import login_view, logout_view


def health(request: HttpRequest) -> JsonResponse:
    """The liveness probe. No database access, by contract."""
    return JsonResponse({"status": "ok"})


def _bundle(request: HttpRequest, view_name: str) -> HttpResponse:
    """The single-page bundle, or the placeholder that stands for it.

    The bundle is built by Vite into `STATIC_ROOT` (task 7.3). Until that
    build exists, a placeholder keeps the route resolvable instead of
    404 - a route that does not exist and a route that is not built yet
    look the same from the outside, and the difference is the difference
    between "the contract is broken" and "the work is pending".

    **The FILE is served, out of the DIRECTORY.** Django's `serve()`
    takes the path of the file RELATIVE to `document_root`: it joins the
    two and refuses to escape the root. So the call is
    `serve(request, "index.html", document_root=STATIC_ROOT)` - the
    directory is the root, and the name inside it is the bundle's entry
    point. Passing the file as the path would look for a file named
    after the directory, inside that directory, and answer a 500.
    """
    raiz = settings.STATIC_ROOT
    indice = raiz / "index.html"
    if indice.exists():
        return serve_static(request, "index.html", document_root=str(raiz))
    return HttpResponse(
        "<!doctype html>"
        '<html lang="es"><head><meta charset="utf-8">'
        f"<title>{view_name}</title></head>"
        f"<body><div id=\"root\" data-route=\"{view_name}\"></div></body></html>",
        content_type="text/html; charset=utf-8",
    )


def asset_del_bundle(request: HttpRequest, nombre: str) -> HttpResponse:
    """`/assets/<name>` - a file of the Vite bundle.

    **The bundle is served BY THE APPLICATION, not by the static files
    machinery.** The reason is the manifest: `collectstatic` writes
    `staticfiles.json` and the production storage
    (`CompressedManifestStaticFilesStorage`) serves STRICTLY from it -
    the bundle is not in `STATICFILES_DIRS`, so `collectstatic` does not
    know about it, and the bundle's assets are not in the manifest.

    With `WHITENOISE_AUTOREFRESH` off - which is the production setting
    - the bundle's URL answered **404**, and the page loaded a bundle
    that could never boot. That is landmine 2, exactly: "the bundle URL
    must return 200, not a blank page".

    So the assets are served HERE, out of `STATIC_ROOT`, by name. The
    name is checked against the bundle's own directory: a path with a
    `..` in it is refused, and only a plain file name is read.

    Serving the bundle from the application also makes the design's claim
    provable: the pages and the API are on the SAME origin because the
    same service serves both (CAC-06).
    """
    raiz = settings.STATIC_ROOT
    # Only a plain file name: a path with a separator or a `..` in it
    # could escape the bundle's directory.
    if not nombre or "/" in nombre or "\\" in nombre or ".." in nombre:
        return HttpResponse(status=404)

    fichero = raiz / "assets" / nombre
    if not fichero.is_file():
        return HttpResponse(status=404)

    return FileResponse(
        fichero.open("rb"),
        content_type=mimetypes.guess_type(str(fichero))[0]
        or "application/octet-stream",
    )


def spa_publico(request: HttpRequest, view_name: str = "") -> HttpResponse:
    """The PUBLIC surface: the bundle, and never a redirect.

    `/app/cliente/` is public - the client reads its statement with a
    credential, not with a session - and the client's page carries no
    CSRF token, because the client has no session for CSRF to protect
    (ADR-4).
    """
    return _bundle(request, view_name)


def spa_staff(request: HttpRequest, view_name: str = "") -> HttpResponse:
    """The STAFF surface: the bundle, or a redirect to the login.

    The staff scope lives in the session, so a request without one has
    no scope and the surface answers "302 to login" - which is what the
    design's route table says.
    """
    from tienda.api.permissions import current_shop

    if current_shop(request) is None:
        return redirect("/login/")
    return _bundle(request, view_name)


def _api_urlpatterns():
    """Build the `/api/v1/…` patterns, tolerating the API's absence.

    `tienda.api.urls` arrives with task 4.21. The import is guarded so the
    project boots and every non-API route keeps working before then; once the
    module exists the mount is picked up with no change here.

    The patterns are included under the namespace **`api`**, so a route is
    reversed as `api:caja` rather than as `caja`. A plain `include()` of a
    list builds an unnamed resolver, and the names inside it are then not
    reversible at all — which would leave the tests unable to name the route
    they exercise. The namespace is the price of `reverse()`.
    """
    try:
        from tienda.api import urls as tienda_api_urls
    except ImportError:
        return []
    return tienda_api_urls.urlpatterns


urlpatterns = [
    path("health/", health, name="health"),
    # The bundle's assets. They are served by the APPLICATION and not by
    # the static files machinery: the production storage serves strictly
    # from the manifest that `collectstatic` writes, and the bundle is
    # not in it - so the bundle's URL answered 404 and the page loaded a
    # bundle that could never boot (landmine 2).
    path(
        "assets/<str:nombre>",
        asset_del_bundle,
        name="asset_del_bundle",
    ),
    # The staff sign-in. It is the route that writes the session's
    # `shop_id` - the one source of the staff scope - and the plan did
    # not have it.
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    # The owner's board: staff, so it redirects to the login without a
    # session.
    path("app/posicion/", lambda request: spa_staff(request, "posicion"), name="app_posicion"),
    # The client's statement: public.
    path("app/cliente/", lambda request: spa_publico(request, "cliente"), name="app_cliente"),
    # The SPA owns its own sub-paths. The shop's screen is
    # `/app/propuesta/{id}/`, so the pattern has to accept a segment with
    # an id in it - not only a word.
    re_path(
        r"^app/(?P<view_name>[a-z\-]+)(?:/(?P<row_id>\d+))?/$",
        lambda request, view_name, row_id=None: spa_staff(request, view_name),
    ),
]

# The API mount is appended last so the explicit routes above always win.
urlpatterns += [path("api/v1/", include("tienda.api.urls"))]
