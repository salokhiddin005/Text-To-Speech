"""CLI entry point: speak text streaming sentence by sentence."""

import sys

from tts.engine import TTSEngine
from tts.player import StreamingPlayer


def main() -> None:
    text = " ".join(sys.argv[1:]) or "Hello, this is my text to speech system."
    print(f"Speaking: {text!r}")

    engine = TTSEngine()
    player = StreamingPlayer()
    try:
        player.play(engine.stream(text))
    except KeyboardInterrupt:
        player.stop()
        print("\nStopped.")


if __name__ == "__main__":
    main()
