"""Flask web server: phone-accessible TTS over your local Wi-Fi."""

import io
import socket

from flask import Flask, jsonify, render_template, request, send_file

from tts import TTSEngine

app = Flask(__name__)
engine = TTSEngine()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="empty text"), 400
    audio = engine.synthesize_to_wav_bytes(text)
    return send_file(io.BytesIO(audio), mimetype="audio/wav")


def _local_ip() -> str:
    """Best-effort guess at this machine's LAN IP, for printing instructions."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main() -> None:
    port = 5000
    ip = _local_ip()
    print()
    print(f"  Open on this laptop:   http://localhost:{port}")
    print(f"  Open from your phone:  http://{ip}:{port}")
    print(f"  (Phone must be on the same Wi-Fi network.)")
    print()
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
