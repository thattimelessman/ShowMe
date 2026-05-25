# ─────────────────────────────────────────
#  ShowMe — core/listener.py
#  The heart of ShowMe.
#  Streams mic audio → Vosk transcription →
#  detects "show me" → fires executor.
#  Runs on its own daemon thread.
# ─────────────────────────────────────────
import time
_last_trigger_time = 0
COOLDOWN_SECONDS = 3
import json
import logging
import threading
import queue

log = logging.getLogger("showme.listener")

# global flag — set to False to stop the listener thread cleanly
_running = threading.Event()
_running.set()

# queue for passing status updates to UI (optional)
status_queue = queue.Queue()


def _post_status(msg: str):
    """Push a status string to the UI queue (non-blocking)."""
    try:
        status_queue.put_nowait(msg)
    except queue.Full:
        pass


def start(app_dict: dict, model_path: str, sample_rate: int, chunk_size: int):
    """
    Main listener loop. Call this on a daemon thread.

    app_dict    — full installed apps dictionary from scanner
    model_path  — path to Vosk model folder
    sample_rate — 16000
    chunk_size  — 4000 frames per read
    """
    # imports here so the module loads even without these packages (e.g. on CI)
    try:
        import vosk
        import pyaudio
    except ImportError as e:
        log.error(f"Missing dependency: {e}. Install vosk and pyaudio.")
        return

    from core.parser   import extract_target
    from core.executor import execute_query

    # ── Load Vosk model ──────────────────
    log.info(f"Loading Vosk model from: {model_path}")
    try:
        model = vosk.Model(model_path)
    except Exception as e:
        log.error(f"Failed to load Vosk model: {e}")
        _post_status("ERROR: Vosk model not found. Download it and place in /model folder.")
        return

    recognizer = vosk.KaldiRecognizer(model, sample_rate)
    recognizer.SetWords(False)   # we don't need word timestamps — saves RAM
   

    # ── Open mic stream ──────────────────
    pa = pyaudio.PyAudio()
    try:
        stream = pa.open(
            rate=sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=chunk_size,
        )
    except Exception as e:
        log.error(f"Failed to open microphone: {e}")
        _post_status("ERROR: Could not access microphone.")
        pa.terminate()
        return

    log.info("ShowMe is listening...")
    _post_status("Listening")

    # ── Main loop ────────────────────────
    try:
        while _running.is_set():
            data = stream.read(chunk_size, exception_on_overflow=False)

            if recognizer.AcceptWaveform(data):
                # full utterance result
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
            else:
                # NEVER trigger on partials — wait for full utterance only
                continue

            if not text:
                continue

            from config import DEBUG_MODE
            if DEBUG_MODE:
                log.debug(f"Heard: {text}")

            # check for trigger phrase
            target = extract_target(text)
            if target:
                global _last_trigger_time
                now = time.time()
                if now - _last_trigger_time < COOLDOWN_SECONDS:
                    log.debug("Cooldown active, ignoring trigger")
                    continue
                _last_trigger_time = now
                log.info(f"Triggered! Target: '{target}'")
                _post_status(f"Opening: {target}")
                threading.Thread(
                    target=execute_query,
                    args=(target, app_dict),
                    daemon=True
                ).start()

    except Exception as e:
        log.error(f"Listener error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        log.info("Listener stopped.")
        _post_status("Stopped")


def stop():
    """Signal the listener loop to exit cleanly."""
    _running.clear()
    log.info("Stop signal sent to listener.")
