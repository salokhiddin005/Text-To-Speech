import hashlib
import hmac
import time

import pytest

import server
from server import MAX_TEXT_CHARS, app, limiter, mint_page_token

from .conftest import TEST_API_KEY

AUTH = {"X-API-Key": TEST_API_KEY}


def page_headers(**extra):
    return {"X-Page-Token": mint_page_token(), **extra}


def expired_page_token() -> str:
    """A correctly signed token whose expiry has already passed."""
    expires = str(int(time.time()) - 1)
    signature = hmac.new(server.SECRET_KEY, expires.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{expires}.{signature}"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    # The suite makes far more synthesis calls than the per-visitor allowance,
    # and they all come from one address; leave the limiter on and tests would
    # fail on the cap rather than on what they are actually asserting. The
    # attribute is what takes effect — setting RATELIMIT_ENABLED after init does
    # not, since the limiter reads it once at construction.
    limiter.enabled = False
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
    res = client.post(
        "/speak", json={"text": "hi"}, headers=page_headers(Origin="https://evil.example.com")
    )
    assert res.status_code == 403
    assert "origin" in res.json["error"]


def test_speak_requires_page_token(client):
    """A scripted caller has no token, so it cannot reach synthesis at all."""
    res = client.post("/speak", json={"text": "hi"})
    assert res.status_code == 403
    assert res.json["code"] == "bad_page_token"


def test_speak_rejects_forged_page_token(client):
    res = client.post(
        "/speak", json={"text": "hi"}, headers={"X-Page-Token": "9999999999.deadbeef"}
    )
    assert res.status_code == 403
    assert res.json["code"] == "bad_page_token"


def test_speak_rejects_expired_page_token(client):
    """Correct signature, but past its expiry — a scraped token goes stale."""
    res = client.post("/speak", json={"text": "hi"}, headers={"X-Page-Token": expired_page_token()})
    assert res.status_code == 403
    assert res.json["code"] == "bad_page_token"


def test_index_is_not_cacheable(client):
    """The page carries a per-visit token; a cached copy serves a stale one."""
    res = client.get("/")
    assert "no-store" in res.headers.get("Cache-Control", "")


def test_index_serves_a_working_page_token(client):
    """The token embedded in the page must be one /speak actually accepts."""
    page = client.get("/").data.decode()
    token = page.split('name="page-token" content="')[1].split('"')[0]
    res = client.post("/speak", json={"text": ""}, headers={"X-Page-Token": token})
    assert res.status_code == 400  # reached the handler; rejected only for empty text


def test_speak_allows_no_origin(client):
    """Non-browser callers send no Origin; the token is what gates them."""
    res = client.post("/speak", json={"text": ""}, headers=page_headers())
    assert res.status_code == 400


def test_speak_allows_same_origin(client):
    """The site's own page (any host/port, including LAN IPs) must work."""
    res = client.post("/speak", json={"text": ""}, headers=page_headers(Origin="http://localhost"))
    assert res.status_code == 400


def test_speak_same_origin_gets_cors_header(client):
    res = client.post("/speak", json={"text": ""}, headers=page_headers(Origin="http://localhost"))
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


def test_text_limit_matches_the_page(client):
    """The counter shown in the UI must be the limit the server enforces."""
    page = client.get("/").data.decode()
    assert f"const MAX_CHARS    = {MAX_TEXT_CHARS};" in page
    assert f"0 / {MAX_TEXT_CHARS}" in page


def test_synthesis_limit_is_enforced_per_visitor():
    """Limiter is disabled in the shared fixture, so exercise it explicitly."""
    app.config["TESTING"] = True
    limiter.enabled = True
    limiter.reset()
    try:
        with app.test_client() as c:
            headers = {"X-API-Key": TEST_API_KEY, "X-Forwarded-For": "203.0.113.7"}
            codes = [
                c.post("/api/speak", json={"text": ""}, headers=headers).status_code
                for _ in range(7)
            ]
            allowed = sum(1 for code in codes if code != 429)
            assert allowed == 5, f"expected 5 through before the cap, got {codes}"
            assert codes[-1] == 429

            # A different visitor still has their own allowance.
            other = {"X-API-Key": TEST_API_KEY, "X-Forwarded-For": "203.0.113.8"}
            assert c.post("/api/speak", json={"text": ""}, headers=other).status_code != 429
    finally:
        limiter.enabled = False
        limiter.reset()


def test_rate_limited_response_says_when_to_retry():
    """Without Retry-After the page can only say 'a while', which is useless
    when the allowance is small."""
    app.config["TESTING"] = True
    limiter.enabled = True
    limiter.reset()
    try:
        with app.test_client() as c:
            headers = {"X-API-Key": TEST_API_KEY, "X-Forwarded-For": "203.0.113.30"}
            last = None
            for _ in range(7):
                last = c.post("/api/speak", json={"text": ""}, headers=headers)
            assert last.status_code == 429
            retry = last.headers.get("Retry-After")
            assert retry is not None, "no Retry-After on a 429"
            assert 0 < int(retry) <= 3600
    finally:
        limiter.enabled = False
        limiter.reset()
