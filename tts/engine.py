"""TTS engine: thin wrapper around PiperVoice with text normalization."""

import io
import wave
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
from piper import PiperVoice

from .normalize import normalize_text

DEFAULT_MODEL = (
    Path(__file__).resolve().parent.parent / "models" / "en_US-amy-medium.onnx"
)


class TTSEngine:
    def __init__(self, model_path: Path = DEFAULT_MODEL):
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. Run: python download_model.py"
            )
        self.voice = PiperVoice.load(str(model_path))

    def stream(self, text: str) -> Iterable[Tuple[np.ndarray, int]]:
        """Yield (audio_int16_array, sample_rate) one chunk per sentence."""
        text = normalize_text(text)
        for chunk in self.voice.synthesize(text):
            yield chunk.audio_int16_array, chunk.sample_rate

    def synthesize_to_file(self, text: str, out_path: Path) -> None:
        text = normalize_text(text)
        with wave.open(str(out_path), "wb") as wav:
            self.voice.synthesize_wav(text, wav)

    def synthesize_to_wav_bytes(self, text: str) -> bytes:
        """Return a complete WAV file in memory. Used by the web server."""
        text = normalize_text(text)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            self.voice.synthesize_wav(text, wav)
        return buf.getvalue()
