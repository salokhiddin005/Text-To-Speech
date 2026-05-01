import pytest

from server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json == {"status": "ok"}


def test_voices_endpoint(client):
    res = client.get("/api/voices")
    assert res.status_code == 200
    data = res.json
    assert "default" in data
    assert "voices" in data
    assert len(data["voices"]) > 0
    assert all("id" in v and "name" in v for v in data["voices"])


def test_speak_empty_text(client):
    res = client.post("/api/speak", json={"text": ""})
    assert res.status_code == 400


def test_speak_unknown_voice(client):
    res = client.post("/api/speak", json={"text": "hi", "voice": "no_such_voice"})
    assert res.status_code == 400


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
