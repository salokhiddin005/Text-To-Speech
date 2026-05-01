"""Flask web server: phone-accessible TTS over your local Wi-Fi.

Also runs on cloud platforms (Render, Hugging Face Spaces, etc.) — set the
PORT environment variable to override the default of 5000.
"""

import io
import os
import socket

from flask import Flask, jsonify, render_template, request, send_file

from tts import TTSEngine
from tts.engine import VOICES, DEFAULT_VOICE_ID

app = Flask(__name__)
engine = TTSEngine()


@app.route("/")
def index():
    return render_template("index.html", voices=VOICES, default_voice=DEFAULT_VOICE_ID)


@app.route("/voices")
def voices():
    return jsonify(voices=VOICES, default=DEFAULT_VOICE_ID)


@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="empty text"), 400

    voice_id = data.get("voice") or DEFAULT_VOICE_ID
    if voice_id not in VOICES:
        return jsonify(error=f"unknown voice {voice_id!r}"), 400

    try:
        speed = float(data.get("speed", 1.0))
    except (TypeError, ValueError):
        speed = 1.0
    speed = max(0.5, min(speed, 2.0))
    length_scale = 1.0 / speed

    audio = engine.synthesize_to_wav_bytes(text, voice_id=voice_id, length_scale=length_scale)
    return send_file(io.BytesIO(audio), mimetype="audio/wav")


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
        print(f"  (Phone must be on the same Wi-Fi network.)")
        print()
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
