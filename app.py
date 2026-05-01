"""Desktop GUI: text box + Speak/Stop buttons."""

import threading
import tkinter as tk
from tkinter import ttk

from tts.engine import TTSEngine
from tts.player import StreamingPlayer

SAMPLE_TEXT = (
    "Hello, this is my text to speech system. "
    "It can read numbers like 1234 and abbreviations like Dr. Smith."
)


class TTSApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Text-to-Speech")
        self.root.geometry("560x380")

        self.engine = TTSEngine()
        self.player = StreamingPlayer()
        self._worker: threading.Thread | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Type or paste text:").pack(anchor="w")

        self.textbox = tk.Text(frame, height=10, wrap="word", font=("Segoe UI", 11))
        self.textbox.pack(fill="both", expand=True, pady=(4, 8))
        self.textbox.insert("1.0", SAMPLE_TEXT)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")

        self.speak_btn = ttk.Button(buttons, text="Speak", command=self._on_speak)
        self.speak_btn.pack(side="left")

        self.stop_btn = ttk.Button(buttons, text="Stop", command=self._on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.clear_btn = ttk.Button(buttons, text="Clear", command=self._on_clear)
        self.clear_btn.pack(side="left", padx=(8, 0))

        self.status = ttk.Label(frame, text="Ready.", foreground="gray")
        self.status.pack(anchor="w", pady=(8, 0))

    def _on_speak(self) -> None:
        text = self.textbox.get("1.0", "end").strip()
        if not text:
            return
        self.speak_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.configure(text="Speaking...")

        def run() -> None:
            try:
                self.player.play(self.engine.stream(text))
            finally:
                self.root.after(0, self._on_done)

        self._worker = threading.Thread(target=run, daemon=True)
        self._worker.start()

    def _on_stop(self) -> None:
        self.player.stop()
        self.status.configure(text="Stopped.")

    def _on_clear(self) -> None:
        self.textbox.delete("1.0", "end")

    def _on_done(self) -> None:
        self.speak_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        if self.status.cget("text") == "Speaking...":
            self.status.configure(text="Ready.")


def main() -> None:
    root = tk.Tk()
    TTSApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
