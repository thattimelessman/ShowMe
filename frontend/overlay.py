# ─────────────────────────────────────────
#  ShowMe — frontend/overlay.py
#  Frameless, transparent, always-on-top
#  notification overlay. Shows briefly then fades.
#  Appears bottom-right of screen.
# ─────────────────────────────────────────

import threading
import logging

log = logging.getLogger("showme.overlay")


def show_overlay(message: str, duration: int = 3):
    """
    Show a floating notification overlay with `message`.
    Auto-dismisses after `duration` seconds.
    Runs in its own thread so it never blocks the listener.
    """
    t = threading.Thread(
        target=_show,
        args=(message, duration),
        daemon=True
    )
    t.start()


def _show(message: str, duration: int):
    try:
        from PyQt6.QtWidgets import QApplication, QLabel, QWidget
        from PyQt6.QtCore    import Qt, QTimer
        from PyQt6.QtGui     import QFont, QScreen
        import sys

        app = QApplication.instance() or QApplication(sys.argv)

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
        QTimer.singleShot(duration * 1000, win.close)
        app.exec()

    except Exception as e:
        log.error(f"Overlay error: {e}")
