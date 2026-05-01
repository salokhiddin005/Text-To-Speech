"""Flask web server: phone-accessible TTS over your local Wi-Fi.

Runs locally and on cloud platforms (Render, Hugging Face Spaces). Set the
PORT environment variable to override the default of 5000.
"""

import io
import os
import socket
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

from tts import TTSEngine
from tts.engine import VOICES, DEFAULT_VOICE_ID

app = Flask(__name__, static_folder="static")
engine = TTSEngine()

# ─────────── usage analytics (in-memory) ───────────
_stats_lock = threading.Lock()
_stats = {"requests": 0, "by_voice": {}, "started_at": datetime.utcnow().isoformat() + "Z"}


def _bump(voice_id: str) -> None:
    with _stats_lock:
        _stats["requests"] += 1
        _stats["by_voice"][voice_id] = _stats["by_voice"].get(voice_id, 0) + 1


# ─────────── pages ───────────
@app.route("/")
def index():
    return render_template("index.html", voices=VOICES, default_voice=DEFAULT_VOICE_ID)


@app.route("/docs")
def docs():
    return render_template("docs.html", voices=VOICES)


# ─────────── PWA static files ───────────
@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.static_folder, "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


# ─────────── core API ───────────
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
    length_scale = 1.0 / speed
    audio = engine.synthesize_to_wav_bytes(text, voice_id=voice_id, length_scale=length_scale)
    _bump(voice_id)
    return audio, None


@app.route("/speak", methods=["POST"])
def speak():
    payload = request.get_json(silent=True) or {}
    audio, err = _do_speak(payload)
    if err:
        msg, status = err
        return jsonify(error=msg), status
    return send_file(io.BytesIO(audio), mimetype="audio/wav")


@app.route("/api/speak", methods=["POST"])
def api_speak():
    """Public API endpoint — same as /speak but documented at /docs."""
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
        return jsonify(_stats)


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
        print()
        print(f"  Open on this laptop:   http://localhost:{port}")
        print(f"  Open from your phone:  http://{ip}:{port}")
        print(f"  API docs:              http://localhost:{port}/docs")
        print()
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
