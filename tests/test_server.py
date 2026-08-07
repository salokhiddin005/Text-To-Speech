import pytest

from server import MAX_TEXT_CHARS, app

from .conftest import TEST_API_KEY

AUTH = {"X-API-Key": TEST_API_KEY}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json["status"] == "ok"
    # Surfaced so a deployment with a mis-set API_KEYS env var is diagnosable
    # from outside without exposing the key.
    assert res.json["api_configured"] is True


def test_voices_endpoint(client):
    res = client.get("/api/voices")
    assert res.status_code == 200
    data = res.json
    assert "default" in data
    assert "voices" in data
    assert len(data["voices"]) > 0
    assert all("id" in v and "name" in v for v in data["voices"])


def test_speak_blocks_disallowed_origin(client):
    res = client.post("/speak", json={"text": "hi"}, headers={"Origin": "https://evil.example.com"})
    assert res.status_code == 403


def test_speak_allows_no_origin(client):
    """curl and backend scripts send no Origin; they must not be blocked."""
    res = client.post("/speak", json={"text": ""})
    assert res.status_code == 400


def test_speak_allows_same_origin(client):
    """The site's own page (any host/port, including LAN IPs) must work."""
    res = client.post("/speak", json={"text": ""}, headers={"Origin": "http://localhost"})
    assert res.status_code == 400


def test_speak_same_origin_gets_cors_header(client):
    res = client.post("/speak", json={"text": ""}, headers={"Origin": "http://localhost"})
    assert res.headers.get("Access-Control-Allow-Origin") == "http://localhost"


def test_speak_missing_api_key(client):
    res = client.post("/api/speak", json={"text": "hi"})
    assert res.status_code == 401


def test_speak_invalid_api_key(client):
    res = client.post("/api/speak", json={"text": "hi"}, headers={"X-API-Key": "wrong-key"})
    assert res.status_code == 401


def test_speak_empty_text(client):
    res = client.post("/api/speak", json={"text": ""}, headers=AUTH)
    assert res.status_code == 400


def test_speak_unknown_voice(client):
    res = client.post(
        "/api/speak",
        json={"text": "hi", "voice": "no_such_voice"},
        headers=AUTH,
    )
    assert res.status_code == 400


def test_speak_rejects_oversized_text(client):
    res = client.post("/api/speak", json={"text": "a" * (MAX_TEXT_CHARS + 1)}, headers=AUTH)
    assert res.status_code == 413


def test_speak_accepts_text_at_the_limit(client):
    """Boundary check: exactly MAX_TEXT_CHARS must not be rejected as too long."""
    res = client.post("/api/speak", json={"text": "a" * MAX_TEXT_CHARS}, headers=AUTH)
    assert res.status_code != 413


def test_speak_missing_model_returns_503(client):
    """A voice in the registry whose .onnx was never downloaded is a normal
    state (download_model.py skips failures) and must not surface as a 500."""
    res = client.post("/api/speak", json={"text": "hi"}, headers=AUTH)
    assert res.status_code in (200, 503)
    if res.status_code == 503:
        assert "not installed" in res.json["error"]


def test_stats_endpoint(client):
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json
    assert "requests" in data
    assert "cache" in data


def test_index_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Text to Speech" in res.data


def test_docs_page(client):
    res = client.get("/docs")
    assert res.status_code == 200
    assert b"/api/speak" in res.data
