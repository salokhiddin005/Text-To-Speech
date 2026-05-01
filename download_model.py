"""Download the en_US-amy-medium Piper voice model into ./models/."""

import sys
import urllib.request
from pathlib import Path

VOICE = "en_US-amy-medium"
BASE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "en/en_US/amy/medium"
)
FILES = [f"{VOICE}.onnx", f"{VOICE}.onnx.json"]
MODELS_DIR = Path(__file__).parent / "models"


def download(filename: str) -> None:
    url = f"{BASE_URL}/{filename}"
    dest = MODELS_DIR / filename
    if dest.exists():
        print(f"  exists: {dest.name}")
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
    print(f"Downloading {VOICE} voice into {MODELS_DIR}/")
    for filename in FILES:
        download(filename)
    print("Done.")


if __name__ == "__main__":
    main()
