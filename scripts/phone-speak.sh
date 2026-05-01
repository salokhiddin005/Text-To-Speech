#!/data/data/com.termux/files/usr/bin/bash
#
# Phone TTS launcher.
# Install at: $PREFIX/bin/speak  (chmod +x)
# Usage:      speak "text to speak"
#
# Pipeline:  Termux -> Ubuntu (proot-distro) -> Piper -> WAV in shared storage
#            Then play the resulting WAV in VLC (or any media player).

set -e

if [ -z "$*" ]; then
  echo "Usage: speak \"text to speak\""
  exit 1
fi

OUT="/storage/emulated/0/speech.wav"
TEXT_FILE="$HOME/.speak_text"

printf '%s' "$*" > "$TEXT_FILE"

echo "Synthesizing..."
proot-distro login ubuntu -- bash -c \
  "cat /data/data/com.termux/files/home/.speak_text | piper --model /root/tts/models/en_US-amy-medium.onnx --output_file $OUT"

echo ""
echo "Done. Open VLC and tap 'speech.wav' from Internal storage."
