"""Streaming audio player.

Synthesis runs in a background thread that fills a small queue while the
main thread plays each chunk. The next sentence is being synthesized while
the current one plays, which keeps gaps between sentences inaudible.
"""

import queue
import threading
from typing import Iterable, Tuple

import numpy as np
import sounddevice as sd

_SENTINEL = object()


class StreamingPlayer:
    def __init__(self, queue_size: int = 4):
        self._queue_size = queue_size
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()
        sd.stop()

    def play(self, chunks: Iterable[Tuple[np.ndarray, int]]) -> None:
        self._stop_event.clear()
        q: queue.Queue = queue.Queue(maxsize=self._queue_size)

        def produce() -> None:
            try:
                for audio, rate in chunks:
                    if self._stop_event.is_set():
                        return
                    q.put((audio, rate))
            finally:
                q.put(_SENTINEL)

        producer = threading.Thread(target=produce, daemon=True)
        producer.start()

        try:
            while not self._stop_event.is_set():
                item = q.get()
                if item is _SENTINEL:
                    return
                audio, rate = item
                sd.play(audio, rate)
                sd.wait()
        finally:
            sd.stop()
            producer.join(timeout=1.0)
