# Text-to-Speech System

An on-device text-to-speech system that runs on **laptops and Android phones**. Uses Piper TTS with American English voices. CPU-only, no GPU, no internet required at runtime.

## What you can do

- **Laptop CLI:** `python speak.py "any text"` — audio plays through speakers
- **Laptop GUI:** desktop window with a text box and Speak/Stop/Clear buttons
- **Web app:** runs on the laptop, accessible from any device's browser on your local Wi-Fi (including your phone)
- **Phone (on-device):** synthesis runs entirely on your Android phone via Termux, fully offline

## Project status

All four stages complete. The phone setup uses Termux + a small Ubuntu container — see the **Phone setup** section below.

## Quick start (laptop)

1. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Download the voice model (~63 MB):
   ```powershell
   python download_model.py
   ```
4. Speak from the command line:
   ```powershell
   python speak.py "say anything you want"
   ```
5. Or open the desktop app:
   ```powershell
   python app.py
   ```
6. Or run the web server (works from your phone's browser too):
   ```powershell
   python server.py
   ```
   The server prints two URLs. Open the `http://<your-laptop-ip>:5000` one on your phone (same Wi-Fi).

## Phone setup (on-device, offline)

Running TTS directly on the phone takes more steps than the laptop because Android isn't a normal Linux environment. The pipeline is: **Termux → Ubuntu (via proot-distro) → Piper → VLC**.

### One-time setup

1. **Install Termux from GitHub** (not Play Store — that version is broken):
   - Phone Chrome → `https://github.com/termux/termux-app/releases/latest`
   - Download the `arm64-v8a.apk` asset
   - Install (allow unknown sources, bypass Play Protect via "More details" → "Install anyway")

2. **Install Termux:API from GitHub** (needed for file-sharing permissions):
   - `https://github.com/termux/termux-api/releases/latest`
   - Download the universal `.apk`
   - Install (same warnings as above)

3. **Install VLC** (any media player works, but VLC is the most reliable):
   - Play Store → search VLC → install **VLC for Android**

4. **Inside Termux**, set up the system:
   ```bash
   pkg update && pkg upgrade -y
   pkg install python git wget proot-distro termux-api nano -y

   # Allow Termux to share files with other apps
   mkdir -p ~/.termux
   echo "allow-external-apps = true" >> ~/.termux/termux.properties
   termux-reload-settings
   termux-setup-storage   # tap Allow on the popup
   ```

5. **Install Ubuntu inside Termux**:
   ```bash
   proot-distro install ubuntu
   proot-distro login ubuntu
   ```

6. **Inside Ubuntu**, install Python and Piper:
   ```bash
   apt update
   apt install -y python3 python3-pip wget
   pip install piper-tts --break-system-packages
   ```

7. **Download the voice model into Ubuntu**:
   ```bash
   mkdir -p /root/tts/models
   cd /root/tts/models
   wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
   wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json
   exit   # back to Termux
   ```

8. **Create the `speak` launcher** (back in Termux):
   ```bash
   nano $PREFIX/bin/speak
   ```
   Paste the contents of [`scripts/phone-speak.sh`](scripts/phone-speak.sh) (also shown below), save with `Ctrl+X` → `Y` → Enter, then:
   ```bash
   chmod +x $PREFIX/bin/speak
   ```

### Daily use on phone

```bash
speak "Hello from my phone."
```

Then open VLC and tap **speech.wav** in Internal storage.

## Project structure

```
.
├── app.py                  # Desktop GUI (Tkinter)
├── speak.py                # CLI entry point (laptop)
├── server.py               # Flask web server
├── templates/
│   └── index.html          # Phone-friendly web page
├── download_model.py       # Downloads Piper voice model
├── requirements.txt
├── scripts/
│   └── phone-speak.sh      # `speak` launcher script for the phone
├── tts/
│   ├── __init__.py
│   ├── engine.py           # PiperVoice wrapper
│   ├── normalize.py        # Text cleanup (numbers, abbreviations, symbols)
│   └── player.py           # Streaming audio player
└── models/                 # Voice files (gitignored)
```

## What gets normalized

- Abbreviations: `Mr.`, `Mrs.`, `Dr.`, `St.`, `etc.`, `i.e.`, `e.g.`, ...
- Symbols: `&`, `@`, `%`, `$`, `+`, `=`, ...
- Numbers: `1234` → "one thousand, two hundred and thirty-four"
- Ordinals: `3rd` → "third", `21st` → "twenty-first"

## How streaming works (laptop)

`PiperVoice.synthesize()` yields one audio chunk per sentence. The `StreamingPlayer` uses a small queue: synthesis runs on a background thread that fills the queue while the main thread plays each chunk. The next sentence is being synthesized while the current one plays, so long text starts speaking quickly and there are no gaps between sentences.

## Why the phone uses a different pipeline

The Piper Python package depends on `onnxruntime`, which doesn't ship prebuilt wheels for Termux on Android. We sidestep this by running a small Ubuntu container *inside* Termux via `proot-distro` — Ubuntu has full glibc, so `pip install piper-tts` just works. Synthesis happens inside Ubuntu; the resulting WAV is written to Android's shared storage where VLC can play it.

## Roadmap

- [x] Stage 1: Laptop hello world
- [x] Stage 2: Clean engine, text normalization, streaming, GUI
- [x] Stage 3: Flask web app accessible from phone browser
- [x] Stage 4A: On-device phone TTS via Termux + Ubuntu + Piper
- [ ] Stage 4B (optional): Native Android APK with home screen icon (Kotlin + Android Studio + sherpa-onnx)
