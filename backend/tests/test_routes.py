"""Route-declaration checks that don't need a running backend or heavy models."""
import inspect

import pytest
from fastapi.params import Path as PathParam
from fastapi.routing import APIRoute


@pytest.fixture(scope="module")
def routes():
    from src.api.routes import app

    return [r for r in app.routes if isinstance(r, APIRoute)]


def _path_params_declared(route: APIRoute) -> set[str]:
    sig = inspect.signature(route.endpoint)
    return {
        name
        for name, p in sig.parameters.items()
        if isinstance(p.default, PathParam)
        or any(isinstance(m, PathParam) for m in getattr(p.annotation, "__metadata__", ()))
    }


def test_every_declared_path_param_appears_in_its_route_path(routes):
    # A Path param missing from the URL template is unsatisfiable: every call 422s.
    offenders = [
        f"{route.path} missing {{{name}}}"
        for route in routes
        for name in _path_params_declared(route)
        if f"{{{name}}}" not in route.path
    ]
    assert offenders == []


def test_scraper_preview_takes_fiction_id_in_the_path(routes):
    paths = {r.path for r in routes}
    assert "/api/scraper/preview/{fiction_id}" in paths
