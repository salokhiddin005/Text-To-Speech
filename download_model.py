"""Download all configured Piper voices into ./models/.

Idempotent and tolerant — already-downloaded files are skipped, and a single
voice failing to download (e.g., URL not found) does not abort the rest.
"""

import sys
import urllib.error
import urllib.request
from pathlib import Path

VOICES = [
    ("en_US-amy-medium", "en/en_US/amy/medium"),
    ("en_US-norman-medium", "en/en_US/norman/medium"),
    ("en_US-lessac-medium", "en/en_US/lessac/medium"),
    ("en_GB-alba-medium", "en/en_GB/alba/medium"),
    ("en_GB-northern_english_male-medium", "en/en_GB/northern_english_male/medium"),
    ("es_ES-davefx-medium", "es/es_ES/davefx/medium"),
    ("fr_FR-siwis-medium", "fr/fr_FR/siwis/medium"),
    ("de_DE-thorsten-medium", "de/de_DE/thorsten/medium"),
    ("it_IT-paola-medium", "it/it_IT/paola/medium"),
    ("pt_BR-faber-medium", "pt/pt_BR/faber/medium"),
    ("ru_RU-irina-medium", "ru/ru_RU/irina/medium"),
    ("ar_JO-kareem-medium", "ar/ar_JO/kareem/medium"),
]
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
MODELS_DIR = Path(__file__).parent / "models"


def download(filename: str, voice_path: str) -> bool:
    url = f"{BASE_URL}/{voice_path}/{filename}"
    dest = MODELS_DIR / filename
    if dest.exists():
        print(f"  exists:      {filename}")
        return True
    print(f"  downloading: {filename}")
    last_percent = -1

    def progress(block_num, block_size, total_size):
        nonlocal last_percent
        downloaded = block_num * block_size
        percent = min(100, downloaded * 100 // max(total_size, 1))
        if percent != last_percent:
            sys.stdout.write(f"\r    {percent:3d}%")
            sys.stdout.flush()
            last_percent = percent

    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress)
        sys.stdout.write("\n")
        return True
    except urllib.error.HTTPError as exc:
        sys.stdout.write(f"\n    SKIPPED: HTTP {exc.code} for {url}\n")
        if dest.exists():
            dest.unlink()
        return False
    except Exception as exc:
        sys.stdout.write(f"\n    SKIPPED: {exc}\n")
        if dest.exists():
            dest.unlink()
        return False


def main() -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    print(f"Downloading {len(VOICES)} voices into {MODELS_DIR}/")
    successes = 0
    for voice_id, voice_path in VOICES:
        ok_onnx = download(f"{voice_id}.onnx", voice_path)
        ok_json = download(f"{voice_id}.onnx.json", voice_path)
        if ok_onnx and ok_json:
            successes += 1
    print(f"Done. {successes}/{len(VOICES)} voices ready.")


if __name__ == "__main__":
    main()
