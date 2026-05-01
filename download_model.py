"""Download all configured Piper voices into ./models/.

Idempotent — already-downloaded files are skipped.
"""

import sys
import urllib.request
from pathlib import Path

VOICES = [
    ("en_US-amy-medium",                       "en/en_US/amy/medium"),
    ("en_US-norman-medium",                    "en/en_US/norman/medium"),
    ("en_US-lessac-medium",                    "en/en_US/lessac/medium"),
    ("en_GB-alba-medium",                      "en/en_GB/alba/medium"),
    ("en_GB-northern_english_male-medium",     "en/en_GB/northern_english_male/medium"),
]
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
MODELS_DIR = Path(__file__).parent / "models"


def download(filename: str, voice_path: str) -> None:
    url = f"{BASE_URL}/{voice_path}/{filename}"
    dest = MODELS_DIR / filename
    if dest.exists():
        print(f"  exists:      {filename}")
        return
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

    urllib.request.urlretrieve(url, dest, reporthook=progress)
    sys.stdout.write("\n")


def main() -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    print(f"Downloading {len(VOICES)} voices into {MODELS_DIR}/")
    for voice_id, voice_path in VOICES:
        download(f"{voice_id}.onnx", voice_path)
        download(f"{voice_id}.onnx.json", voice_path)
    print("Done.")


if __name__ == "__main__":
    main()
