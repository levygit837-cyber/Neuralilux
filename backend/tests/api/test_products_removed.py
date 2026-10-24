"""A pilha legada de Products foi removida (#82): a rota não existe mais."""
import pytest


@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/products"),
    ("get", "/api/v1/products/"),
    ("post", "/api/v1/products/"),
    ("get", "/api/v1/products/abc"),
    ("put", "/api/v1/products/abc"),
    ("delete", "/api/v1/products/abc"),
])
def test_products_route_returns_404(client, auth_headers, method, path):
    response = getattr(client, method)(path, headers=auth_headers)
    assert response.status_code == 404
