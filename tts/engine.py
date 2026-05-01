"""TTS engine: thin wrapper around PiperVoice with text normalization.

Supports multiple voices via lazy loading — only the most recently used voice
stays in memory, which keeps RAM usage low enough for free-tier hosts (Render's
512 MB plan).
"""

import io
import wave
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
from piper import PiperVoice

from .normalize import normalize_text

DEFAULT_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_VOICE_ID = "en_US-amy-medium"

VOICES = {
    "en_US-amy-medium":                    "Amy - English (US Female)",
    "en_US-norman-medium":                 "Norman - English (US Male)",
    "en_US-lessac-medium":                 "Lessac - English (US Female)",
    "en_GB-alba-medium":                   "Alba - English (UK Female)",
    "en_GB-northern_english_male-medium":  "Northern - English (UK Male)",
    "es_ES-davefx-medium":                 "Davefx - Spanish",
    "fr_FR-siwis-medium":                  "Siwis - French",
    "de_DE-thorsten-medium":               "Thorsten - German",
    "it_IT-paola-medium":                  "Paola - Italian",
    "pt_BR-faber-medium":                  "Faber - Portuguese (Brazil)",
    "ru_RU-irinia-medium":                 "Irina - Russian",
    "ar_JO-kareem-medium":                 "Kareem - Arabic",
}


class TTSEngine:
    def __init__(self, models_dir: Path = DEFAULT_MODELS_DIR, cache_size: int = 1):
        self.models_dir = Path(models_dir)
        self._cache_size = cache_size
        self._cache: dict[str, PiperVoice] = {}

    def _get_voice(self, voice_id: str) -> PiperVoice:
        if voice_id in self._cache:
            return self._cache[voice_id]
        model_path = self.models_dir / f"{voice_id}.onnx"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Voice '{voice_id}' not found at {model_path}. "
                f"Run download_model.py to fetch missing voices."
            )
        if len(self._cache) >= self._cache_size:
            self._cache.clear()
        voice = PiperVoice.load(str(model_path))
        self._cache[voice_id] = voice
        return voice

    def _make_config(self, length_scale: float):
        try:
            from piper.config import SynthesisConfig
            return SynthesisConfig(length_scale=length_scale)
        except (ImportError, TypeError):
            return None

    def stream(
        self, text: str, voice_id: str = DEFAULT_VOICE_ID, length_scale: float = 1.0
    ) -> Iterable[Tuple[np.ndarray, int]]:
        voice = self._get_voice(voice_id)
        text = normalize_text(text)
        config = self._make_config(length_scale)
        kwargs = {"syn_config": config} if config is not None else {}
        for chunk in voice.synthesize(text, **kwargs):
            yield chunk.audio_int16_array, chunk.sample_rate

    def synthesize_to_wav_bytes(
        self, text: str, voice_id: str = DEFAULT_VOICE_ID, length_scale: float = 1.0
    ) -> bytes:
        voice = self._get_voice(voice_id)
        text = normalize_text(text)
        config = self._make_config(length_scale)
        kwargs = {"syn_config": config} if config is not None else {}
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            voice.synthesize_wav(text, wav, **kwargs)
        return buf.getvalue()

    def available_voices(self) -> list[str]:
        """Voices that have actually been downloaded (model file exists)."""
        return [vid for vid in VOICES if (self.models_dir / f"{vid}.onnx").exists()]
