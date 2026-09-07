# Authored by Vedanti Kanade
# Written by: [Your Name] - SJSU CMPE-272
import hmac
import hashlib
import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from main import app
from config import settings

client = TestClient(app)

def generate_signature(payload: str, secret: str) -> str:
    """Helper to generate valid HMAC SHA-256 signatures for testing."""
    digest = hmac.new(secret.encode("utf-8"), msg=payload.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"

# 1. Health Check Endpoint Test
def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "ok"

# 2. Webhook Signature Verification Tests
def test_webhook_invalid_signature():
    payload = json.dumps({"action": "opened"})
    headers = {
        "X-Hub-Signature-256": "sha256=invalid_hash",
        "X-GitHub-Event": "issues",
        "X-GitHub-Delivery": "test-delivery-001"
    }
    response = client.post("/webhook", content=payload, headers=headers)
    assert response.status_code == 401
    assert "Invalid HMAC signature" in response.json()["detail"]

def test_webhook_valid_ping_event():
    payload = json.dumps({"zen": "Responsive is better than fast."})
    sig = generate_signature(payload, settings.WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "test-ping-del-1"
    }
    response = client.post("/webhook", content=payload, headers=headers)
    assert response.status_code == 204

def test_webhook_unsupported_event():
    payload = json.dumps({"action": "pushed"})
    sig = generate_signature(payload, settings.WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "test-push-del-1"
    }
    response = client.post("/webhook", content=payload, headers=headers)
    assert response.status_code == 400

# 3. Events Audit Trail Test
def test_events_endpoint():
    response = client.get("/events")
    assert response.status_code == 200
    assert "events" in response.json()

# 4. Mock Proxy Endpoint Tests
@patch("github_client.create_github_issue", new_callable=AsyncMock)
def test_create_issue_endpoint(mock_create):
    mock_create.return_value = {
        "number": 42,
        "html_url": "https://github.com/owner/repo/issues/42",
        "state": "open",
        "title": "Bug in authentication",
        "body": "Detailed description",
        "labels": [{"name": "bug"}],
        "created_at": "2026-09-06T00:00:00Z",
        "updated_at": "2026-09-06T00:00:00Z"
    }

    payload = {"title": "Bug in authentication", "body": "Detailed description", "labels": ["bug"]}
    response = client.post("/issues", json=payload)
    
    assert response.status_code == 201
    assert response.json()["number"] == 42
    assert response.headers["Location"] == "/issues/42"

@patch("github_client.list_github_issues", new_callable=AsyncMock)
def test_list_issues_endpoint(mock_list):
    mock_list.return_value = (200, [
        {
            "number": 1,
            "title": "Test Issue",
            "state": "open",
            "labels": [{"name": "enhancement"}],
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2026-09-06T00:00:00Z",
            "updated_at": "2026-09-06T00:00:00Z"
        }
    ], {"ETag": 'W/"12345"'})

    response = client.get("/issues")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["number"] == 1