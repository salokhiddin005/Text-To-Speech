"""Flask web server: phone-accessible TTS over your local Wi-Fi.

Runs locally and on cloud platforms (Render, Hugging Face Spaces). Set the
PORT environment variable to override the default of 5000.
"""

import hashlib
import hmac
import io
import logging
import os
import secrets
import socket
import threading
import time
from datetime import UTC, datetime
from functools import lru_cache, wraps
from urllib.parse import urlparse

from flask import (
    Flask,
    jsonify,
    make_response,
    render_template,
    request,
    send_file,
    send_from_directory,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from tts import TTSEngine
from tts.engine import DEFAULT_VOICE_ID, VOICES

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


MAX_TEXT_CHARS = 700

# Synthesis is the expensive path and the one worth protecting. Counters are held
# in memory, so a restart clears them — on a free tier that sleeps when idle the
# window is best-effort rather than a guarantee.
SYNTHESIS_LIMIT = "5 per hour"


def _split_env_list(name: str) -> set[str]:
    return {item.strip() for item in os.environ.get(name, "").split(",") if item.strip()}


# Gate the public /api/speak endpoint (not the website's own /speak). Left empty
# the endpoint reports itself as unconfigured rather than silently accepting a
# key nobody knows — a misconfigured deployment should be obvious, not subtle.
API_KEYS = _split_env_list("API_KEYS")
if not API_KEYS:
    logger.warning("API_KEYS not set - /api/speak is disabled until it is configured")

# Extra origins allowed to call /speak from browser JS. Same-origin requests are
# always permitted, so this only needs entries for genuine cross-origin callers.
EXTRA_ALLOWED_ORIGINS = {origin.rstrip("/") for origin in _split_env_list("ALLOWED_ORIGINS")}

# Signing key for page tokens. Generated per-process when unset, which is fine
# for a single worker; set SECRET_KEY explicitly before scaling past one, or
# tokens minted by one worker will be rejected by the others.
SECRET_KEY = os.environ.get("SECRET_KEY", "").encode() or secrets.token_bytes(32)

# How long a page token stays valid. Long enough that an open tab rarely expires,
# short enough that a scraped token has to be refreshed to stay useful.
PAGE_TOKEN_TTL = 2 * 60 * 60


def mint_page_token() -> str:
    """Issue a token embedded in the served page.

    /speak has to stay open for ordinary visitors, so it can't sit behind an API
    key — but that also makes it scriptable. Requiring a signed token that only
    the rendered page hands out means a would-be integrator has to load the real
    page and re-scrape on every expiry instead of just calling the endpoint.
    Signed rather than stored, so it costs no memory and survives no state.
    """
    expires = str(int(time.time()) + PAGE_TOKEN_TTL)
    signature = hmac.new(SECRET_KEY, expires.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{expires}.{signature}"


def _page_token_is_valid(token: str) -> bool:
    expires, _, signature = (token or "").partition(".")
    if not expires or not signature:
        return False
    expected = hmac.new(SECRET_KEY, expires.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        return int(expires) > time.time()
    except ValueError:
        return False


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not API_KEYS:
            return jsonify(error="API key auth is not configured on this deployment"), 503
        if request.headers.get("X-API-Key") not in API_KEYS:
            return jsonify(error="missing or invalid API key"), 401
        return view(*args, **kwargs)

    return wrapped


app = Flask(__name__, static_folder="static")

# Behind Render and Hugging Face the address Flask sees is the platform's proxy,
# which is the same for every visitor — so the per-IP rate limit would put the
# whole world in one bucket, and a handful of visitors would lock out everyone.
# Trusting the forwarded client address restores per-visitor limits. Only x_for
# is fixed up: request.host already resolves correctly and the origin check
# depends on it. PORT is set by both platforms and not by a plain local run.
TRUST_PROXY = os.environ.get(
    "TRUST_PROXY", "1" if "PORT" in os.environ else "0"
).strip().lower() not in ("0", "false", "no", "")
if TRUST_PROXY:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

engine = TTSEngine()


def _is_allowed_origin(origin: str) -> bool:
    """Compare against the request's own host rather than a hardcoded list, so
    the LAN/phone workflow keeps working: a page served at http://192.168.1.5:5000
    sends exactly that as its Origin, and hardcoding deployment URLs would 403 it.
    """
    if origin.rstrip("/") in EXTRA_ALLOWED_ORIGINS:
        return True
    return urlparse(origin).netloc == request.host


@app.before_request
def _block_cross_origin_speak():
    """Let the site's own pages call /speak, but stop other sites' client-side JS
    from embedding it. Non-browser callers (curl, backend scripts) send no Origin
    header at all, so this doesn't affect them — /api/speak + API keys cover those.
    """
    if request.path == "/speak":
        origin = request.headers.get("Origin")
        if origin and not _is_allowed_origin(origin):
            logger.warning("blocked cross-origin /speak request from %s", origin)
            return jsonify(error="requests from this origin are not allowed"), 403


@app.after_request
def _apply_cors_headers(response):
    origin = request.headers.get("Origin")
    if request.path == "/speak" and origin and _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response


limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",
    # Sends Retry-After and X-RateLimit-*; without them a refused caller has no
    # way to know when their allowance returns, and the page can only say
    # "try again later" rather than naming a time.
    headers_enabled=True,
)

_stats_lock = threading.Lock()
_stats: dict = {
    "requests": 0,
    "by_voice": {},
    "started_at": datetime.now(UTC).isoformat(),
}


def _bump(voice_id: str) -> None:
    with _stats_lock:
        _stats["requests"] += 1
        _stats["by_voice"][voice_id] = _stats["by_voice"].get(voice_id, 0) + 1


# Each entry holds a full WAV in memory (~0.5-1 MB for a full-length request), and
# a loaded voice model already costs ~150 MB, so keep this modest on 512 MB hosts.
@lru_cache(maxsize=32)
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
    page = render_template(
        "index.html",
        voices=VOICES,
        default_voice=DEFAULT_VOICE_ID,
        page_token=mint_page_token(),
    )
    response = make_response(page)
    # This page carries a per-visit token, so it must never be served from a
    # browser or CDN cache — a stale copy hands out an expired token.
    response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


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
    if len(text) > MAX_TEXT_CHARS:
        # Synthesis time scales with length and a worker is blocked throughout,
        # so an unbounded request would take the whole instance down with it.
        return None, (f"text exceeds {MAX_TEXT_CHARS} characters", 413)
    voice_id = payload.get("voice") or DEFAULT_VOICE_ID
    if voice_id not in VOICES:
        return None, (f"unknown voice {voice_id!r}", 400)
    try:
        speed = float(payload.get("speed", 1.0))
    except (TypeError, ValueError):
        speed = 1.0
    speed = max(0.5, min(speed, 2.0))
    length_scale = round(1.0 / speed, 3)
    try:
        audio = _synthesize_cached(text, voice_id, length_scale)
    except FileNotFoundError:
        # Configured in VOICES but never downloaded — download_model.py skips
        # voices it can't fetch, so this is a normal state, not a server bug.
        logger.error("voice %s is configured but its model file is missing", voice_id)
        return None, (f"voice {voice_id!r} is not installed on this server", 503)
    _bump(voice_id)
    return audio, None


@app.route("/speak", methods=["POST"])
@limiter.limit(SYNTHESIS_LIMIT)
def speak():
    # Only the page this server rendered can reach synthesis here; scripts and
    # copied curl commands have no way to produce a valid token. /api/speak is
    # the supported path for programmatic callers, and it needs an API key.
    if not _page_token_is_valid(request.headers.get("X-Page-Token", "")):
        logger.warning("rejected /speak with missing or expired page token")
        return jsonify(error="invalid or expired page token", code="bad_page_token"), 403
    payload = request.get_json(silent=True) or {}
    audio, err = _do_speak(payload)
    if err:
        msg, status = err
        logger.warning("speak rejected: %s", msg)
        return jsonify(error=msg), status
    return send_file(io.BytesIO(audio), mimetype="audio/wav")


@app.route("/api/speak", methods=["POST"])
@limiter.limit(SYNTHESIS_LIMIT)
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
    # api_configured reports whether API_KEYS reached the process, so a bad env
    # var can be spotted from outside without ever exposing the key itself.
    return {"status": "ok", "api_configured": bool(API_KEYS)}


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
