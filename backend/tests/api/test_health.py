"""
API health check tests.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Welcome to Scheme Saathi API"
    assert "docs" in data
    assert "health" in data


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"
    assert body["data"]["service"] == "Scheme Saathi API"
    assert "timestamp" in body["data"]
    assert body["error"] is None
    assert "request_id" in body


def test_health_check_has_version():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert "version" in body["data"]


def test_unknown_route_returns_404():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
