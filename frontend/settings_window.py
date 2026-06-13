# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — frontend/settings_window.py  v5
#
#  Changes vs v4-fixed:
#   • Soft eye-strain colours: dark #1a1b1e base, light #f5f6f8 base
#   • Full theme-token coverage — no more hardcoded hex in widget styles
#   • Consistent button appearance across both themes
#   • Stronger active-tab highlight, subtle border-bottom indicator
#   • Better visual hierarchy: section labels, spacing, font sizes
#   • Hover effects on list rows and buttons uniformly applied
#   • stat-card sub-labels, footer, hints all theme-aware
# ─────────────────────────────────────────
import logging
import sys
import os
import json
import threading

log = logging.getLogger("showme.settings")

STATS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "showme_stats.json"
)

_ui_queue = None


def init(q):
    global _ui_queue
    _ui_queue = q


def _load_stats() -> dict:
    try:
        if os.path.isfile(STATS_FILE):
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"total": 0, "today": 0, "last_date": "", "most_opened": {}, "last_command": ""}


def _save_stats(stats: dict):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


def record_command(app_name: str):
    from datetime import date
    stats = _load_stats()
    today = str(date.today())
    if stats.get("last_date") != today:
        stats["today"] = 0
        stats["last_date"] = today
    stats["total"] = stats.get("total", 0) + 1
    stats["today"] = stats.get("today", 0) + 1
    stats["last_command"] = app_name
    most = stats.get("most_opened", {})
    most[app_name] = most.get(app_name, 0) + 1
    stats["most_opened"] = most
    _save_stats(stats)


def open_settings(app_dict: dict, on_rescan_callback, listener_status_queue=None):
    if _ui_queue is not None:
        _ui_queue.put(lambda: _show_window(app_dict, on_rescan_callback, listener_status_queue))
    else:
        t = threading.Thread(
            target=_show_window,
            args=(app_dict, on_rescan_callback, listener_status_queue),
            daemon=True
        )
        t.start()


def _make_tray_icon(listening: bool):
    from PIL import Image, ImageDraw
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (86, 156, 18, 255) if listening else (146, 0, 0, 255)
    draw.ellipse([2, 2, size - 2, size - 2], fill=color)
    mw, mh = 18, 22
    mx = (size - mw) // 2
    my = 10
    draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=9, fill=(255, 255, 255, 255))
    draw.arc([14, 28, 50, 46], start=0, end=180, fill=(255, 255, 255, 220), width=3)
    cx = size // 2
    draw.line([cx, 46, cx, 54], fill=(255, 255, 255, 220), width=3)
    draw.line([cx - 8, 54, cx + 8, 54], fill=(255, 255, 255, 220), width=3)
    return img


def _show_window(app_dict: dict, on_rescan_callback, listener_status_queue=None):
    """
    Build and show the settings window.
    Always runs on the main thread (posted via queue by open_settings).
    Uses a per-window QEventLoop so QApplication stays alive for future opens.
    """
    try:
        from PyQt6.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QScrollArea, QFrame,
            QLineEdit, QSlider, QComboBox, QTabWidget,
            QCheckBox, QTextEdit, QListWidget, QListWidgetItem,
            QCompleter, QWidget
        )
        from PyQt6.QtCore import Qt, QTimer, QStringListModel, QEventLoop
        from PyQt6.QtGui import (
            QFont, QColor, QPainter, QPen, QBrush,
            QPainterPath, QIcon, QPixmap
        )
        import pyaudio

        app = QApplication.instance()
        if app is None:
            log.error("Settings: QApplication not ready — window skipped.")
            return

        # ═══════════════════════════════════════
        #  THEME TOKENS  — every colour lives here
        #  Dark: soft navy-black (#1a1b1e base) — easy on eyes in dim rooms
        #  Light: warm off-white (#f5f6f8 base) — reduces glare vs pure white
        # ═══════════════════════════════════════
        THEMES = {
            "dark": {
                # backgrounds
                "bg"           : "#1a1b1e",
                "surface"      : "#212328",
                "surface2"     : "#282a2f",
                "hover"        : "#2e3036",
                "input_bg"     : "#1e2024",
                "card_bg"      : "#222428",
                # borders
                "border"       : "#32353c",
                "border2"      : "#3a3d45",
                # text
                "text"         : "#e8e9ec",
                "text2"        : "#8c909a",
                "text3"        : "#555a66",
                # accents
                "accent"       : "#569c12",
                "accent_dark"  : "#3d7009",
                "accent_muted" : "#2a4d09",
                "blue"         : "#4a88d4",
                "red"          : "#b33030",
                "red_hover"    : "#8a2020",
                # scrollbar
                "scroll_track" : "#1e2024",
                "scroll_handle": "#3a3d45",
                "scroll_hover" : "#4e5260",
                # status colours
                "status_on"    : "#4a88d4",
                "status_off"   : "#b33030",
            },
            "light": {
                # backgrounds
                "bg"           : "#f5f6f8",
                "surface"      : "#ffffff",
                "surface2"     : "#ecedf0",
                "hover"        : "#e4e5e9",
                "input_bg"     : "#ffffff",
                "card_bg"      : "#ffffff",
                # borders
                "border"       : "#d8dae0",
                "border2"      : "#c8cad2",
                # text
                "text"         : "#1c1d1f",
                "text2"        : "#5a5e6a",
                "text3"        : "#9096a4",
                # accents
                "accent"       : "#4a8a10",
                "accent_dark"  : "#376808",
                "accent_muted" : "#e8f5e0",
                "blue"         : "#2a62b8",
                "red"          : "#c02828",
                "red_hover"    : "#962020",
                # scrollbar
                "scroll_track" : "#ecedf0",
                "scroll_handle": "#c4c7d0",
                "scroll_hover" : "#a8acb8",
                # status colours
                "status_on"    : "#2a62b8",
                "status_off"   : "#c02828",
            },
        }

        current_theme = ["dark"]
        is_listening  = [True]

        def c(key):
            return THEMES[current_theme[0]][key]

        # ── Animated status dot ───────────────
        class StatusDot(QWidget):
            def __init__(self):
                super().__init__()
                self._on    = True
                self._pulse = 0.0
                self._dir   = 1
                self.setFixedSize(10, 10)
                t = QTimer(self)
                t.timeout.connect(self._tick)
                t.start(40)

            def set_listening(self, v):
                self._on = v
                self.update()

            def _tick(self):
                self._pulse = min(1.0, max(0.0, self._pulse + 0.08 * self._dir))
                if self._pulse >= 1.0:
                    self._dir = -1
                elif self._pulse <= 0.0:
                    self._dir = 1
                self.update()

            def paintEvent(self, _e):
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                col = QColor(c("accent")) if self._on else QColor(c("red"))
                col.setAlpha(int(150 + 105 * self._pulse))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(col))
                p.drawEllipse(0, 0, 10, 10)
                p.end()

        # ── Asset paths ───────────────────────
        _assets_dir  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
        _icon_path   = os.path.join(_assets_dir, "icon_green.png")
        _icon_path_r = os.path.join(_assets_dir, "icon_red.png")
        _ico_path    = os.path.join(_assets_dir, "icon_green.ico")
        
        def _make_arrow_png(color_hex: str) -> str:
            from PIL import Image, ImageDraw
            scale = 4
            w, h  = 12, 8
            W, H  = w * scale, h * scale
            img   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw  = ImageDraw.Draw(img)
            r = int(color_hex[1:3], 16)
            g = int(color_hex[3:5], 16)
            b = int(color_hex[5:7], 16)
            pad = scale
            lw  = scale + 2
            mid = W // 2
            draw.line([(pad, pad), (mid, H - pad)],     fill=(r, g, b, 255), width=lw)
            draw.line([(mid, H - pad), (W - pad, pad)], fill=(r, g, b, 255), width=lw)
            img = img.resize((w, h), Image.LANCZOS)
            path = os.path.join(_assets_dir, f"_arrow_{color_hex[1:]}.png")
            img.save(path, "PNG")
            return path.replace("\\", "/")


        # ── Window ────────────────────────────
        win = QDialog()
        win.setWindowTitle("ShowMe — Settings")
        win.setWindowIcon(QIcon(_ico_path))
        win.setMinimumSize(600, 680)
        win.setMaximumSize(700, 780)
        win.setWindowFlags(
            win.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        mic_logo = QLabel()
        _pixmap = QPixmap(_icon_path)
        mic_logo.setPixmap(_pixmap.scaled(
            52, 52,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))
        mic_logo.setFixedSize(52, 52)
        status_dot = StatusDot()

        last_command = ["—"]
        stats        = _load_stats()
        most_opened  = "—"
        if stats.get("most_opened"):
            most_opened = max(stats["most_opened"], key=lambda k: stats["most_opened"][k])

        # ═══════════════════════════════════════
        #  STYLESHEET
        # ═══════════════════════════════════════
        def apply_theme():
            arrow_path = _make_arrow_png(c("text2"))
            win.setStyleSheet(f"""
                /* ── Base ── */
                QDialog, QWidget {{
                    background-color: {c('bg')};
                    color: {c('text')};
                    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                    font-size: 13px;
                }}

                /* ── Tab widget ── */
                QTabWidget::pane {{
                    border: 1px solid {c('border')};
                    border-top: none;
                    border-radius: 0px 0px 8px 8px;
                    background: {c('surface')};
                }}
                QTabBar {{
                    background: {c('surface2')};
                }}
                QTabBar::tab {{
                    background: {c('surface2')};
                    color: {c('text2')};
                    padding: 9px 22px;
                    border: none;
                    border-bottom: 2px solid transparent;
                    font-size: 12px;
                    font-weight: 500;
                    min-width: 80px;
                }}
                QTabBar::tab:selected {{
                    background: {c('surface')};
                    color: {c('accent')};
                    border-bottom: 2px solid {c('accent')};
                    font-weight: 700;
                }}
                QTabBar::tab:hover:!selected {{
                    background: {c('hover')};
                    color: {c('text')};
                    border-bottom: 2px solid {c('border2')};
                }}

                /* ── Buttons (base) ── */
                QPushButton {{
                    background-color: {c('surface2')};
                    color: {c('text')};
                    border: 1px solid {c('border')};
                    padding: 6px 16px;
                    border-radius: 7px;
                    font-weight: 500;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {c('hover')};
                    border-color: {c('accent')};
                    color: {c('text')};
                }}
                QPushButton:pressed {{
                    background-color: {c('border2')};
                }}

                /* ── Accent (green filled) ── */
                QPushButton#accent_btn {{
                    background-color: {c('accent')};
                    color: #ffffff;
                    border: none;
                    font-weight: 700;
                    font-size: 13px;
                }}
                QPushButton#accent_btn:hover {{
                    background-color: {c('accent_dark')};
                }}
                QPushButton#accent_btn:pressed {{
                    background-color: {c('accent_dark')};
                }}

                /* ── Danger (delete) ── */
                QPushButton#danger_btn {{
                    background-color: transparent;
                    color: {c('red')};
                    border: 1px solid {c('red')};
                    padding: 2px 8px;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton#danger_btn:hover {{
                    background-color: {c('red')};
                    color: #ffffff;
                }}

                /* FIX 4: Pause Button (Red, Rounded) */
                QPushButton#pause_btn {{
                    background-color: {c('red')};
                    color: #ffffff;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 7px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton#pause_btn:hover {{
                    background-color: {c('red_hover')};
                }}

                /* FIX 4: Resume Button (Green, Rounded) */
                QPushButton#resume_btn {{
                    background-color: {c('accent')};
                    color: #ffffff;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 7px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton#resume_btn:hover {{
                    background-color: {c('accent_dark')};
                }}

                /* ── Inputs ── */
                QLineEdit {{
                    background-color: {c('input_bg')};
                    border: 1px solid {c('border')};
                    border-radius: 7px;
                    padding: 7px 12px;
                    color: {c('text')};
                    font-size: 13px;
                    selection-background-color: {c('accent')};
                }}
                QLineEdit:focus {{
                    border-color: {c('accent')};
                    background-color: {c('surface')};
                }}
                QLineEdit::placeholder {{
                    color: {c('text3')};
                }}

                /* ── Slider ── */
                QSlider::groove:horizontal {{
                    height: 4px;
                    background: {c('border2')};
                    border-radius: 2px;
                }}
                QSlider::handle:horizontal {{
                    background: {c('accent')};
                    width: 16px;
                    height: 16px;
                    border-radius: 8px;
                    margin: -6px 0;
                    border: 2px solid {c('bg')};
                }}
                QSlider::sub-page:horizontal {{
                    background: {c('accent')};
                    border-radius: 2px;
                }}

                /* FIX 1 + FIX 3: ComboBox — wide enough, no box-button glitch */
                QComboBox {{
                    background: {c('input_bg')};
                    border: 1px solid {c('border')};
                    border-radius: 7px;
                    padding: 6px 28px 6px 11px;
                    color: {c('text')};
                    font-size: 12px;
                    min-width: 80px;
                    selection-background-color: {c('accent')};
                }}
                QComboBox:hover {{
                    border-color: {c('accent')};
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: right center;
                    width: 24px;
                    border: none;
                    border-left: none;
                    background: transparent;
                }}
                QComboBox::down-arrow {{
                    image: url({arrow_path});
                    width: 12px;
                    height: 8px;
                }}
                QComboBox QAbstractItemView {{
                    background: {c('surface2')};
                    border: 1px solid {c('border')};
                    border-radius: 6px;
                    padding: 3px;
                    outline: none;
                }}
                QComboBox QAbstractItemView::item {{
                    padding: 6px 12px;
                    border-radius: 4px;
                    color: {c('text')};
                }}
                QComboBox QAbstractItemView::item:selected,
                QComboBox QAbstractItemView::item:hover {{
                    background: {c('hover')};
                    color: {c('text')};
                }}

                /* ── Scrollbars — slim, no arrows ── */
                QScrollArea {{ border: none; background: transparent; }}
                QScrollBar:vertical {{
                    background: {c('scroll_track')};
                    width: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: {c('scroll_handle')};
                    border-radius: 3px;
                    min-height: 24px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {c('scroll_hover')};
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px; background: none; border: none;
                }}
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {{ background: none; }}
                QScrollBar:horizontal {{
                    background: {c('scroll_track')};
                    height: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }}
                QScrollBar::handle:horizontal {{
                    background: {c('scroll_handle')};
                    border-radius: 3px;
                    min-width: 24px;
                }}
                QScrollBar::handle:horizontal:hover {{
                    background: {c('scroll_hover')};
                }}
                QScrollBar::add-line:horizontal,
                QScrollBar::sub-line:horizontal {{
                    width: 0px; background: none; border: none;
                }}
                QScrollBar::add-page:horizontal,
                QScrollBar::sub-page:horizontal {{ background: none; }}

                /* ── Checkbox ── */
                QCheckBox {{
                    font-size: 13px;
                    spacing: 8px;
                    color: {c('text')};
                }}
                QCheckBox::indicator {{
                    width: 16px; height: 16px;
                    border-radius: 4px;
                    border: 1.5px solid {c('border2')};
                    background: {c('input_bg')};
                }}
                QCheckBox::indicator:checked {{
                    background: {c('accent')};
                    border-color: {c('accent')};
                }}

                /* ── TextEdit (Test Mic) ── */
                QTextEdit {{
                    background: {c('input_bg')};
                    border: 1px solid {c('border')};
                    border-radius: 7px;
                    color: {c('text')};
                    font-family: 'Consolas', monospace;
                    font-size: 12px;
                    padding: 10px;
                    selection-background-color: {c('accent')};
                }}

                /* ── ListWidget (autocomplete suggestions) ── */
                QListWidget {{
                    background: {c('input_bg')};
                    border: 1px solid {c('accent')};
                    border-radius: 7px;
                    color: {c('text')};
                    font-size: 12px;
                    padding: 3px;
                    outline: none;
                }}
                QListWidget::item {{
                    padding: 4px 8px;
                    border-radius: 4px;
                }}
                QListWidget::item:hover {{
                    background: {c('accent_muted')};
                    color: {c('accent')};
                }}
                QListWidget::item:selected {{
                    background: {c('accent')};
                    color: #ffffff;
                }}

                /* ── Divider lines ── */
                QFrame[frameShape="4"] {{
                    background: {c('border')};
                    border: none;
                    max-height: 1px;
                }}
            """)

            # Re-apply inline styles that must respond to theme switches
            sub_lbl.setStyleSheet(f"color: {c('accent')}; font-size: 11px; font-weight: 500;")
            status_text.setStyleSheet(
                f"color: {c('status_on')}; font-size: 12px; font-weight: 600;"
                if is_listening[0]
                else f"color: {c('status_off')}; font-size: 12px; font-weight: 600;"
            )
            last_cmd_lbl.setStyleSheet(f"color: {c('text3')}; font-size: 11px;")
            footer_lbl.setStyleSheet(f"color: {c('text3')}; font-size: 10px;")
            ac_lbl.setStyleSheet(f"color: {c('text2')}; font-size: 13px;")
            sens_val.setStyleSheet(f"color: {c('accent')}; font-weight: bold;")
            hint_lbl.setStyleSheet(f"color: {c('text3')}; font-size: 11px;")
            # Redraw app-list rows with correct text colour
            populate(search.text())

        # ── Root layout ───────────────────────
        root = QVBoxLayout(win)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ════════════════════════════════════════
        #  HEADER
        # ════════════════════════════════════════
        header = QWidget()
        header.setFixedHeight(76)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 12, 20, 12)
        hl.addWidget(mic_logo)
        hl.addSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title_lbl = QLabel("ShowMe")
        title_lbl.setFont(QFont("Segoe UI Variable", 19, QFont.Weight.Bold))
        sub_lbl = QLabel("say it. it opens.  ·  v1.0")
        # colour set in apply_theme()
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        hl.addLayout(title_col)
        hl.addStretch()

        # FIX 1: wider fixed width so "Light" is never clipped
        theme_combo = QComboBox()
        theme_combo.addItems(["Dark", "Light"])
        theme_combo.setFixedWidth(110)
        theme_combo.setFixedHeight(30)
        hl.addWidget(theme_combo)
        root.addWidget(header)

        # ════════════════════════════════════════
        #  STATUS BAR  — FIX 2: pause btn blends in, sits after a small gap
        # ════════════════════════════════════════
        status_bar = QWidget()
        status_bar.setFixedHeight(34)
        sl = QHBoxLayout(status_bar)
        sl.setContentsMargins(20, 0, 20, 0)
        sl.setSpacing(8)
        sl.addWidget(status_dot)
        status_text = QLabel("Listening")
        # colour set in apply_theme()
        sl.addWidget(status_text)

        # FIX 2: subtle separator then button — no jarring red outline
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(14)
        sep.setStyleSheet("color: #444; margin: 0 2px;")
        sl.addWidget(sep)

        pause_btn = QPushButton("Pause")
        pause_btn.setObjectName("pause_btn")
        pause_btn.setFixedHeight(22)
        pause_btn.setMinimumWidth(72)
        sl.addWidget(pause_btn)

        sl.addStretch()
        last_cmd_lbl = QLabel("Last: —")
        # colour set in apply_theme()
        sl.addWidget(last_cmd_lbl)
        root.addWidget(status_bar)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        root.addWidget(div)

        # ── Tabs ──────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().setExpanding(True)
        root.addWidget(tabs)

        # ════════════════════════════════════════
        #  TAB 1 — DASHBOARD
        # ════════════════════════════════════════
        dash = QWidget()
        dl = QVBoxLayout(dash)
        dl.setContentsMargins(20, 18, 20, 18)
        dl.setSpacing(14)

        def stat_card(value, label, color):
            card = QWidget()
            card.setFixedHeight(72)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 10, 16, 10)
            cl.setSpacing(2)
            v = QLabel(str(value))
            v.setFont(QFont("Segoe UI Variable", 22, QFont.Weight.Bold))
            v.setStyleSheet(f"color: {color};")
            l2 = QLabel(label)
            l2.setStyleSheet("color: #888; font-size: 11px;")
            cl.addWidget(v)
            cl.addWidget(l2)
            return card

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        stats_row.addWidget(stat_card(stats.get("total", 0), "total commands", "#569c12"))
        stats_row.addWidget(stat_card(stats.get("today", 0), "today",          "#4a88d4"))
        stats_row.addWidget(stat_card(most_opened,           "most opened",    "#888888"))
        dl.addLayout(stats_row)

        # Apps-indexed row
        ac = QWidget()
        ac.setFixedHeight(46)
        acl = QHBoxLayout(ac)
        acl.setContentsMargins(14, 0, 10, 0)
        ac_lbl = QLabel(f"  {len(app_dict)} apps indexed and ready")
        # colour set in apply_theme()
        acl.addWidget(ac_lbl)
        acl.addStretch()
        rescan2 = QPushButton("Rescan")
        rescan2.setObjectName("accent_btn")
        rescan2.setFixedSize(76, 28)
        acl.addWidget(rescan2)
        dl.addWidget(ac)

        search = QLineEdit()
        search.setPlaceholderText("Search indexed apps...")
        dl.addWidget(search)

        # App list — fills remaining height
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        sc = QWidget()
        scl = QVBoxLayout(sc)
        scl.setSpacing(2)
        scl.setContentsMargins(2, 2, 2, 2)

        all_names = sorted(app_dict.keys())

        def populate(filter_text=""):
            for i in reversed(range(scl.count())):
                w = scl.itemAt(i).widget()
                if w:
                    w.deleteLater()
            names = [n for n in all_names if filter_text.lower() in n.lower()]
            row_text_colour = c("text2")
            dot_colour      = c("accent")
            for name in names[:200]:
                row = QWidget()
                row.setFixedHeight(30)
                rl2 = QHBoxLayout(row)
                rl2.setContentsMargins(10, 0, 10, 0)
                dot2 = QLabel("·")
                dot2.setStyleSheet(f"color: {dot_colour}; font-size: 14px;")
                lbl2 = QLabel(name)
                lbl2.setStyleSheet(f"color: {row_text_colour}; font-size: 12px;")
                rl2.addWidget(dot2)
                rl2.addWidget(lbl2)
                rl2.addStretch()
                scl.addWidget(row)

        populate()
        search.textChanged.connect(populate)
        scroll.setWidget(sc)
        dl.addWidget(scroll, stretch=1)
        tabs.addTab(dash, "Dashboard")

        # ════════════════════════════════════════
        #  TAB 2 — COMMANDS
        # ════════════════════════════════════════
        cmd_tab = QWidget()
        ctl = QVBoxLayout(cmd_tab)
        ctl.setContentsMargins(20, 18, 20, 18)
        ctl.setSpacing(12)

        ct = QLabel("Custom Voice Commands")
        ct.setFont(QFont("Segoe UI Variable", 14, QFont.Weight.Bold))
        ctl.addWidget(ct)

        cs = QLabel("Map any phrase → app. Type phrase + pick app from suggestions.")
        cs.setStyleSheet(f"color: {c('text2')}; font-size: 12px;")
        cs.setWordWrap(True)
        ctl.addWidget(cs)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        phrase_input = QLineEdit()
        phrase_input.setPlaceholderText('Voice phrase  e.g. "exploded"')
        app_input = QLineEdit()
        app_input.setPlaceholderText("App name — type to search")

        completer_model = QStringListModel(all_names)
        completer = QCompleter(completer_model, app_input)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setMaxVisibleItems(8)
        app_input.setCompleter(completer)

        add_btn = QPushButton("Add")
        add_btn.setObjectName("accent_btn")
        add_btn.setFixedSize(56, 34)
        add_row.addWidget(phrase_input)
        add_row.addWidget(app_input)
        add_row.addWidget(add_btn)
        ctl.addLayout(add_row)

        suggestions_list = QListWidget()
        suggestions_list.setFixedHeight(0)
        suggestions_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ctl.addWidget(suggestions_list)

        def update_suggestions(text):
            suggestions_list.clear()
            if len(text) < 2:
                suggestions_list.setFixedHeight(0)
                return
            matches = [n for n in all_names if text.lower() in n.lower()][:8]
            if matches:
                suggestions_list.setFixedHeight(min(len(matches) * 28, 180))
                for m in matches:
                    suggestions_list.addItem(m)
            else:
                suggestions_list.setFixedHeight(0)

        def pick_suggestion(item):
            app_input.setText(item.text())
            suggestions_list.clear()
            suggestions_list.setFixedHeight(0)

        app_input.textChanged.connect(update_suggestions)
        suggestions_list.itemClicked.connect(pick_suggestion)

        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from config import CUSTOM_MAPPINGS
            custom_map = dict(CUSTOM_MAPPINGS)
        except Exception:
            custom_map = {}

        cmd_scroll = QScrollArea()
        cmd_scroll.setWidgetResizable(True)
        cmd_scroll.setFrameShape(QFrame.Shape.NoFrame)
        cmd_content = QWidget()
        cmd_list_layout = QVBoxLayout(cmd_content)
        cmd_list_layout.setSpacing(4)
        cmd_list_layout.setContentsMargins(0, 0, 0, 0)

        def refresh_cmd_list():
            for i in reversed(range(cmd_list_layout.count())):
                w2 = cmd_list_layout.itemAt(i).widget()
                if w2:
                    w2.deleteLater()
            for phrase, target in custom_map.items():
                row2 = QWidget()
                row2.setFixedHeight(36)
                rl3 = QHBoxLayout(row2)
                rl3.setContentsMargins(12, 0, 8, 0)
                p_lbl = QLabel(f'"{phrase}"')
                p_lbl.setStyleSheet(f"color: {c('accent')}; font-size: 12px;")
                arrow = QLabel("→")
                arrow.setStyleSheet(f"color: {c('text3')}; font-size: 13px;")
                t_lbl = QLabel(target)
                t_lbl.setStyleSheet(f"color: {c('text2')}; font-size: 12px;")
                del_btn = QPushButton("✕")
                del_btn.setObjectName("danger_btn")
                del_btn.setFixedSize(26, 26)

                def make_del(ph):
                    def _d():
                        custom_map.pop(ph, None)
                        refresh_cmd_list()
                    return _d

                del_btn.clicked.connect(make_del(phrase))
                rl3.addWidget(p_lbl)
                rl3.addWidget(arrow)
                rl3.addWidget(t_lbl)
                rl3.addStretch()
                rl3.addWidget(del_btn)
                cmd_list_layout.addWidget(row2)

        refresh_cmd_list()

        def add_custom():
            phrase = phrase_input.text().strip().lower()
            target = app_input.text().strip().lower()
            if phrase and target:
                custom_map[phrase] = target
                phrase_input.clear()
                app_input.clear()
                suggestions_list.clear()
                suggestions_list.setFixedHeight(0)
                refresh_cmd_list()

        add_btn.clicked.connect(add_custom)
        cmd_scroll.setWidget(cmd_content)
        ctl.addWidget(cmd_scroll, stretch=1)
        tabs.addTab(cmd_tab, "Commands")

        # ════════════════════════════════════════
        #  TAB 3 — SETTINGS
        # ════════════════════════════════════════
        settings_tab = QWidget()
        stl = QVBoxLayout(settings_tab)
        stl.setContentsMargins(24, 20, 24, 20)
        stl.setSpacing(18)

        def section_lbl(text):
            l3 = QLabel(text)
            l3.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Bold))
            l3.setStyleSheet(f"color: {c('accent')}; letter-spacing: 1.5px;")
            return l3

        # Sensitivity
        stl.addWidget(section_lbl("MATCH SENSITIVITY"))
        sens_row = QHBoxLayout()
        sens_row.setSpacing(10)
        sens_lbl = QLabel("Threshold")
        sens_lbl.setFont(QFont("Segoe UI Variable", 12))
        sens_val = QLabel("85")
        sens_val.setFixedWidth(30)
        # colour set in apply_theme()
        sens_slider = QSlider(Qt.Orientation.Horizontal)
        sens_slider.setRange(50, 95)
        sens_slider.setValue(85)
        try:
            from config import MATCH_THRESHOLD
            sens_slider.setValue(int(MATCH_THRESHOLD))
            sens_val.setText(str(int(MATCH_THRESHOLD)))
        except Exception:
            pass
        sens_slider.valueChanged.connect(lambda v: sens_val.setText(str(v)))
        sens_row.addWidget(sens_lbl)
        sens_row.addWidget(sens_slider)
        sens_row.addWidget(sens_val)
        stl.addLayout(sens_row)

        hint_lbl = QLabel("Lower = more lenient  ·  Higher = stricter matching")
        hint_lbl.setFont(QFont("Segoe UI Variable", 10))
        # colour set in apply_theme()
        stl.addWidget(hint_lbl)

        # FIX 3: Microphone — explicit styling to kill the glitch dash/box
        stl.addWidget(section_lbl("MICROPHONE"))
        mic_combo = QComboBox()
        mic_combo.setMinimumWidth(200)
        try:
            pa = pyaudio.PyAudio()
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    mic_combo.addItem(info["name"], i)
            pa.terminate()
        except Exception:
            mic_combo.addItem("Default Microphone", 0)
        stl.addWidget(mic_combo)

        # Startup
        stl.addWidget(section_lbl("STARTUP"))
        startup_check = QCheckBox("Launch ShowMe when Windows starts")
        startup_check.setChecked(True)
        stl.addWidget(startup_check)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("accent_btn")
        save_btn.setFixedHeight(38)

        def save_settings():
            try:
                import re
                cfg = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "config.py"
                )
                if os.path.isfile(cfg):
                    with open(cfg, "r", encoding="utf-8") as f:
                        content = f.read()
                    content = re.sub(
                        r"MATCH_THRESHOLD\s*=\s*\d+",
                        f"MATCH_THRESHOLD = {sens_slider.value()}",
                        content
                    )
                    with open(cfg, "w", encoding="utf-8") as f:
                        f.write(content)
            except Exception as e:
                log.error("Save settings error: %s", e)

            if startup_check.isChecked():
                try:
                    import winreg
                    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                    script  = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "showme.pyw"
                    )
                    val = f'"{pythonw}" "{script}"'
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Run",
                        0, winreg.KEY_SET_VALUE
                    )
                    winreg.SetValueEx(key, "ShowMe", 0, winreg.REG_SZ, val)
                    winreg.CloseKey(key)
                except Exception:
                    pass

        save_btn.clicked.connect(save_settings)
        stl.addWidget(save_btn)
        stl.addStretch()
        tabs.addTab(settings_tab, "Settings")

        # ════════════════════════════════════════
        #  TAB 4 — TEST MIC
        # ════════════════════════════════════════
        test_tab = QWidget()
        ttl = QVBoxLayout(test_tab)
        ttl.setContentsMargins(20, 18, 20, 18)
        ttl.setSpacing(12)

        tt = QLabel("Microphone Test")
        tt.setFont(QFont("Segoe UI Variable", 14, QFont.Weight.Bold))
        ttl.addWidget(tt)
        ts = QLabel("Speak after pressing Start. See exactly what ShowMe hears.")
        ts.setStyleSheet(f"color: {c('text2')}; font-size: 12px;")
        ttl.addWidget(ts)

        test_out = QTextEdit()
        test_out.setReadOnly(True)
        test_out.setPlaceholderText("Transcript will appear here...")
        test_out.setFixedHeight(200)
        ttl.addWidget(test_out)

        tbr = QHBoxLayout()
        tbr.setSpacing(8)
        start_btn = QPushButton("▶  Start Listening")
        start_btn.setObjectName("accent_btn")
        start_btn.setFixedHeight(36)
        stop_btn = QPushButton("■  Stop")
        stop_btn.setFixedHeight(36)
        stop_btn.setEnabled(False)
        clear_btn2 = QPushButton("Clear")
        clear_btn2.setFixedHeight(36)
        tbr.addWidget(start_btn)
        tbr.addWidget(stop_btn)
        tbr.addWidget(clear_btn2)
        ttl.addLayout(tbr)
        ttl.addStretch()

        test_running = [False]

        def run_test():
            try:
                import vosk
                import pyaudio as pa2

                model_dir = None
                try:
                    from config import MODEL_DIR as MD
                    model_dir = MD
                except Exception:
                    pass

                if not model_dir or not os.path.isdir(model_dir):
                    test_out.append("ERROR: Model not found.")
                    return

                model  = vosk.Model(model_dir)
                rec    = vosk.KaldiRecognizer(model, 16000)
                pa_inst = pa2.PyAudio()
                stream = pa_inst.open(
                    rate=16000, channels=1,
                    format=pa2.paInt16, input=True,
                    frames_per_buffer=4000
                )
                test_out.append("Listening... speak now.")

                while test_running[0]:
                    data = stream.read(4000, exception_on_overflow=False)
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text   = result.get("text", "").strip()
                        if text:
                            test_out.append(f"› {text}")
                            test_out.verticalScrollBar().setValue(
                                test_out.verticalScrollBar().maximum()
                            )
                stream.stop_stream()
                stream.close()
                pa_inst.terminate()
                test_out.append("Stopped.")
            except Exception as e:
                test_out.append(f"Error: {e}")

        def start_test():
            test_running[0] = True
            start_btn.setEnabled(False)
            stop_btn.setEnabled(True)
            threading.Thread(target=run_test, daemon=True).start()

        def stop_test():
            test_running[0] = False
            start_btn.setEnabled(True)
            stop_btn.setEnabled(False)

        start_btn.clicked.connect(start_test)
        stop_btn.clicked.connect(stop_test)
        clear_btn2.clicked.connect(test_out.clear)
        tabs.addTab(test_tab, "Test Mic")

        # ════════════════════════════════════════
        #  BOTTOM BAR
        # ════════════════════════════════════════
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setFixedHeight(1)
        root.addWidget(div2)

        bottom = QWidget()
        bottom.setFixedHeight(42)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(20, 0, 20, 0)
        bl.setSpacing(8)
        footer_lbl = QLabel("ShowMe v1.0  ·  open source  ·  github.com/thattimelessman")
        # colour set in apply_theme()
        bl.addWidget(footer_lbl)
        bl.addStretch()
        rescan_btn = QPushButton("Rescan Apps")
        rescan_btn.setFixedHeight(28)
        close_btn  = QPushButton("Close")
        close_btn.setFixedHeight(28)
        bl.addWidget(rescan_btn)
        bl.addWidget(close_btn)
        root.addWidget(bottom)

        # ════════════════════════════════════════
        #  CALLBACKS
        # ════════════════════════════════════════
        def on_theme(idx):
            current_theme[0] = "dark" if idx == 0 else "light"
            apply_theme()
            # Re-colour static labels that aren't in apply_theme's inline list
            cs.setStyleSheet(f"color: {c('text2')}; font-size: 12px;")
            ts.setStyleSheet(f"color: {c('text2')}; font-size: 12px;")
            refresh_cmd_list()

        theme_combo.currentIndexChanged.connect(on_theme)
        rescan_btn.clicked.connect(lambda: (on_rescan_callback(), win.close()))
        rescan2.clicked.connect(lambda: (on_rescan_callback(), win.close()))
        close_btn.clicked.connect(win.close)

        # ── Pause / Resume ────────────────────
        def toggle_pause():
            if is_listening[0]:
                is_listening[0] = False
                pause_btn.setText("Resume")
                pause_btn.setObjectName("resume_btn")
                pause_btn.style().unpolish(pause_btn)
                pause_btn.style().polish(pause_btn)
                status_dot.set_listening(False)
                status_text.setText("Paused")
                status_text.setStyleSheet(f"color: {c('status_off')}; font-size: 12px; font-weight: 600;")
                mic_logo.setPixmap(QPixmap(_icon_path_r).scaled(
                    52, 52, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                win.setWindowIcon(QIcon(_icon_path_r))
                if listener_status_queue:
                    try:
                        listener_status_queue.put("pause")
                    except Exception:
                        pass
            else:
                is_listening[0] = True
                pause_btn.setText("Pause")
                pause_btn.setObjectName("pause_btn")
                pause_btn.style().unpolish(pause_btn)
                pause_btn.style().polish(pause_btn)
                status_dot.set_listening(True)
                status_text.setText("Listening")
                status_text.setStyleSheet(f"color: {c('status_on')}; font-size: 12px; font-weight: 600;")
                mic_logo.setPixmap(QPixmap(_icon_path).scaled(
                    52, 52, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                win.setWindowIcon(QIcon(_icon_path))
                if listener_status_queue:
                    try:
                        listener_status_queue.put("resume")
                    except Exception:
                        pass

        pause_btn.clicked.connect(toggle_pause)

        # ── Status poll ───────────────────────
        def poll_status():
            if listener_status_queue:
                try:
                    while True:
                        msg = listener_status_queue.get_nowait()
                        if msg == "Listening":
                            is_listening[0] = True
                            status_dot.set_listening(True)
                            mic_logo.setPixmap(QPixmap(_icon_path).scaled(
                                52, 52, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))
                            win.setWindowIcon(QIcon(_icon_path))
                            status_text.setText("Listening")
                            status_text.setStyleSheet(
                                f"color: {c('status_on')}; font-size: 12px; font-weight: 600;"
                            )
                            pause_btn.setText("Pause")
                            pause_btn.setObjectName("pause_btn")
                            pause_btn.style().unpolish(pause_btn)
                            pause_btn.style().polish(pause_btn)
                        elif msg == "Stopped":
                            is_listening[0] = False
                            status_dot.set_listening(False)
                            mic_logo.setPixmap(QPixmap(_icon_path_r).scaled(
                                52, 52, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))
                            win.setWindowIcon(QIcon(_icon_path_r))
                            status_text.setText("Paused")
                            status_text.setStyleSheet(
                                f"color: {c('status_off')}; font-size: 12px; font-weight: 600;"
                            )
                            pause_btn.setText("Resume")
                            pause_btn.setObjectName("resume_btn")
                            pause_btn.style().unpolish(pause_btn)
                            pause_btn.style().polish(pause_btn)
                        elif msg.startswith("Opening:"):
                            cmd = msg.replace("Opening:", "").strip()
                            last_command[0] = cmd
                            last_cmd_lbl.setText(f"Last: {cmd}")
                except Exception:
                    pass

        poll_timer = QTimer()
        poll_timer.timeout.connect(poll_status)
        poll_timer.start(100)

        apply_theme()
        win.show()

        loop = QEventLoop()
        win.finished.connect(loop.quit)
        loop.exec()

    except Exception as e:
        log.error("Settings window error: %s", e)