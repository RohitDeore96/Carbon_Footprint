"""Tests for the health check endpoint and security header enforcement."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(name="client")
def fixture_test_client() -> TestClient:
    """Provide a TestClient instance bound to the application."""
    return TestClient(app)


@pytest.mark.unit
def test_health_endpoint_returns_200(client: TestClient) -> None:
    """Verify GET /health returns HTTP 200 with expected JSON payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data: dict[str, str] = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"


@pytest.mark.security
def test_health_response_contains_csp_header(client: TestClient) -> None:
    """Verify the Content-Security-Policy header is present in the response."""
    response = client.get("/health")
    assert "content-security-policy" in response.headers
    assert "default-src 'self'" in response.headers["content-security-policy"]


@pytest.mark.security
def test_health_response_contains_x_frame_options(client: TestClient) -> None:
    """Verify the X-Frame-Options header is set to DENY."""
    response = client.get("/health")
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.security
def test_health_response_contains_hsts_header(client: TestClient) -> None:
    """Verify the Strict-Transport-Security header is present with correct directives."""
    response = client.get("/health")
    hsts_value: str = response.headers["strict-transport-security"]
    assert "max-age=31536000" in hsts_value
    assert "includeSubDomains" in hsts_value
    assert "preload" in hsts_value


@pytest.mark.security
def test_health_response_contains_content_type_options(client: TestClient) -> None:
    """Verify the X-Content-Type-Options header is set to nosniff."""
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.security
def test_health_response_contains_referrer_policy(client: TestClient) -> None:
    """Verify the Referrer-Policy header is set correctly."""
    response = client.get("/health")
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.security
def test_health_response_contains_permissions_policy(client: TestClient) -> None:
    """Verify the Permissions-Policy header restricts browser features."""
    response = client.get("/health")
    policy: str = response.headers["permissions-policy"]
    assert "geolocation=()" in policy
    assert "microphone=()" in policy
    assert "camera=()" in policy
