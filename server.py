"""Flask web server: phone-accessible TTS over your local Wi-Fi.

Runs locally and on cloud platforms (Render, Hugging Face Spaces). Set the
PORT environment variable to override the default of 5000.
"""

import io
import logging
import os
import secrets
import socket
import threading
from datetime import datetime
from functools import lru_cache, wraps

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from tts import TTSEngine
from tts.engine import DEFAULT_VOICE_ID, VOICES

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _load_api_keys() -> set[str]:
    """API keys gate the public /api/speak endpoint (not the website's own /speak).

    Configure via the API_KEYS env var (comma-separated) for a stable key across
    restarts. If unset, a random key is generated for this process and logged —
    fine for local testing, but callers will need a new key every restart.
    """
    raw = os.environ.get("API_KEYS", "")
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    if not keys:
        generated = secrets.token_urlsafe(24)
        keys = {generated}
        logger.warning(
            "API_KEYS not set - generated a temporary key for this run: %s "
            "(set the API_KEYS env var for a key that survives restarts)",
            generated,
        )
    return keys


API_KEYS = _load_api_keys()


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        key = request.headers.get("X-API-Key")
        if key not in API_KEYS:
            return jsonify(error="missing or invalid API key"), 401
        return view(*args, **kwargs)

    return wrapped


app = Flask(__name__, static_folder="static")
engine = TTSEngine()

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",
)

_stats_lock = threading.Lock()
_stats: dict = {
    "requests": 0,
    "by_voice": {},
    "started_at": datetime.utcnow().isoformat() + "Z",
}


def _bump(voice_id: str) -> None:
    with _stats_lock:
        _stats["requests"] += 1
        _stats["by_voice"][voice_id] = _stats["by_voice"].get(voice_id, 0) + 1


@lru_cache(maxsize=128)
def _synthesize_cached(text: str, voice_id: str, length_scale: float) -> bytes:
    """Cache key: (text, voice_id, length_scale). Returns full WAV bytes."""
    logger.info(
        "synthesize voice=%s len_scale=%.3f chars=%d",
        voice_id,
        length_scale,
        len(text),
    )
    return engine.synthesize_to_wav_bytes(text, voice_id=voice_id, length_scale=length_scale)


@app.route("/")
def index():
    return render_template("index.html", voices=VOICES, default_voice=DEFAULT_VOICE_ID)


@app.route("/docs")
def docs():
    return render_template("docs.html", voices=VOICES)


@app.route("/manifest.json")
def manifest():
    return send_from_directory(
        app.static_folder, "manifest.json", mimetype="application/manifest+json"
    )


@app.route("/sw.js")
def service_worker():
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


def _do_speak(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        return None, ("empty text", 400)
    voice_id = payload.get("voice") or DEFAULT_VOICE_ID
    if voice_id not in VOICES:
        return None, (f"unknown voice {voice_id!r}", 400)
    try:
        speed = float(payload.get("speed", 1.0))
    except (TypeError, ValueError):
        speed = 1.0
    speed = max(0.5, min(speed, 2.0))
    length_scale = round(1.0 / speed, 3)
    audio = _synthesize_cached(text, voice_id, length_scale)
    _bump(voice_id)
    return audio, None


@app.route("/speak", methods=["POST"])
@limiter.limit("30 per minute")
def speak():
    payload = request.get_json(silent=True) or {}
    audio, err = _do_speak(payload)
    if err:
        msg, status = err
        logger.warning("speak rejected: %s", msg)
        return jsonify(error=msg), status
    return send_file(io.BytesIO(audio), mimetype="audio/wav")


@app.route("/api/speak", methods=["POST"])
@limiter.limit("30 per minute")
@require_api_key
def api_speak():
    """Public API endpoint — same as /speak but documented at /docs, and requires
    an X-API-Key header (see API_KEYS env var)."""
    payload = request.get_json(silent=True) or {}
    audio, err = _do_speak(payload)
    if err:
        msg, status = err
        return jsonify(error=msg), status
    return send_file(io.BytesIO(audio), mimetype="audio/wav")


@app.route("/api/voices")
def api_voices():
    available = engine.available_voices()
    return jsonify(
        default=DEFAULT_VOICE_ID,
        voices=[{"id": vid, "name": VOICES[vid], "available": vid in available} for vid in VOICES],
    )


@app.route("/api/stats")
def api_stats():
    with _stats_lock:
        cache_info = _synthesize_cached.cache_info()
        return jsonify(
            **_stats,
            cache={
                "hits": cache_info.hits,
                "misses": cache_info.misses,
                "size": cache_info.currsize,
                "max": cache_info.maxsize,
            },
        )


@app.route("/health")
def health():
    return {"status": "ok"}


def _local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main() -> None:
    port = int(os.environ.get("PORT", 5000))
    if "PORT" not in os.environ:
        ip = _local_ip()
        logger.info("Local:  http://localhost:%d", port)
        logger.info("Phone:  http://%s:%d", ip, port)
        logger.info("Docs:   http://localhost:%d/docs", port)
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
