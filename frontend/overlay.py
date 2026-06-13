# ─────────────────────────────────────────
#  ShowMe — frontend/overlay.py
#  Frameless, transparent, always-on-top
#  notification overlay. Shows briefly then fades.
#  Appears bottom-right of screen.
#
#  Fix: overlay no longer spawns its own thread or creates a
#  QApplication. main.py calls init(queue) once at startup;
#  show_overlay() posts _show() onto the main-thread queue so
#  Qt is only ever touched from the thread that owns QApplication.
# ─────────────────────────────────────────

import threading
import logging

log = logging.getLogger("showme.overlay")

# Set by main.py via init() before any overlay is shown.
_ui_queue = None


def init(q):
    """
    Wire this module to the main-thread UI dispatch queue.
    Must be called once from main.py before show_overlay() is used.
    """
    global _ui_queue
    _ui_queue = q


def show_overlay(message: str, duration: int = 3):
    """
    Show a floating notification overlay with `message`.
    Posts work onto the main-thread queue — Qt is never
    touched from a background thread.
    """
    if _ui_queue is not None:
        _ui_queue.put(lambda: _show(message, duration))
    else:
        # Fallback if called before init() (e.g. tests / early startup)
        t = threading.Thread(target=_show, args=(message, duration), daemon=True)
        t.start()


def _show(message: str, duration: int):
    """
    Runs on the main thread (posted via queue).
    QApplication already exists — just create the widget and show it.
    No app.exec() needed; the main thread's Qt loop handles events.
    """
    try:
        from PyQt6.QtWidgets import QApplication, QLabel, QWidget
        from PyQt6.QtCore    import Qt, QTimer
        from PyQt6.QtGui     import QFont, QScreen

        app = QApplication.instance()
        if app is None:
            log.error("Overlay: QApplication not ready — overlay skipped.")
            return

        win = QWidget()
        win.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.SplashScreen
        )
        win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        label = QLabel(message, win)
        label.setFont(QFont("Segoe UI", 11))
        label.setStyleSheet("""
            QLabel {
                background-color: rgba(15, 15, 15, 210);
                color: #ffffff;
                padding: 12px 20px;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.08);
            }
        """)
        label.adjustSize()

        # position bottom-right
        screen = QScreen.availableGeometry(app.primaryScreen())
        x = screen.width()  - label.width()  - 30
        y = screen.height() - label.height() - 60
        win.setGeometry(x, y, label.width(), label.height())

        win.show()
        # Close after duration — QTimer fires on the main Qt loop.
        # No app.exec() needed here.
        QTimer.singleShot(duration * 1000, win.close)

    except Exception as e:
        log.error(f"Overlay error: {e}")