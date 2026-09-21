"""
Tests for the health-check endpoint.

Covers:
1. HTTP 200 status code
2. Response body schema validation
3. Correct status field value
4. Application name and version in response
5. Environment field presence
6. Timestamp field presence
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    """Health endpoint must return HTTP 200 OK."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_status_is_ok(client: AsyncClient):
    """Health endpoint must return status='ok'."""
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_response_has_app_name(client: AsyncClient):
    """Health response must contain a non-empty app_name."""
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "app_name" in data
    assert len(data["app_name"]) > 0


@pytest.mark.asyncio
async def test_health_response_has_version(client: AsyncClient):
    """Health response must contain a version string."""
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "version" in data
    assert len(data["version"]) > 0


@pytest.mark.asyncio
async def test_health_response_has_environment(client: AsyncClient):
    """Health response must contain an environment string."""
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_response_has_timestamp(client: AsyncClient):
    """Health response must contain a timestamp field."""
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "timestamp" in data
    assert data["timestamp"] is not None


@pytest.mark.asyncio
async def test_health_response_content_type_is_json(client: AsyncClient):
    """Health endpoint must return application/json content type."""
    response = await client.get("/api/v1/health")
    assert "application/json" in response.headers["content-type"]
