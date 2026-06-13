# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — frontend/settings_window.py  v4
#
#  Fixes vs v3:
#   [1] Alpha overflow (StatusDot): _pulse clamped to [0.0, 1.0]
#       so setAlpha() never receives a value > 255. (kept from v3)
#
#   [2] Thread-safety (definitive fix):
#       open_settings() no longer spawns a background thread.
#       Instead it posts _show_window onto the main-thread queue
#       (provided by main.py via init()). _show_window() therefore
#       always runs on the thread that owns QApplication.
#
#   [3] Reopen crash fix:
#       _show_window() uses a per-window QEventLoop instead of
#       app.exec(). The loop quits when the window is destroyed,
#       leaving QApplication alive and reusable for every subsequent
#       open — no more "QApplication not created in main() thread".
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

# Set by main.py via init() before any settings window is opened.
_ui_queue = None


def init(q):
    """
    Wire this module to the main-thread UI dispatch queue.
    Must be called once from main.py before open_settings() is used.
    """
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
    """
    Request the settings window to open.
    If init() was called (normal runtime), posts onto the main-thread queue.
    Falls back to the old thread pattern if called before init() (tests etc).
    """
    if _ui_queue is not None:
        _ui_queue.put(lambda: _show_window(app_dict, on_rescan_callback, listener_status_queue))
    else:
        # Fallback — pre-init / testing only
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

    Uses a per-window QEventLoop so:
      - The window is fully interactive (events processed).
      - QApplication is NOT consumed — it stays alive for future opens.
      - No "QApplication not created in main() thread" on second open.
    """
    try:
        from PyQt6.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QScrollArea, QFrame,
            QLineEdit, QSlider, QComboBox, QTabWidget,
            QCheckBox, QTextEdit, QListWidget, QListWidgetItem,
            QCompleter
        )
        from PyQt6.QtCore import Qt, QTimer, QStringListModel, QEventLoop
        from PyQt6.QtGui import (
            QFont, QColor, QPainter, QPen, QBrush,
            QPainterPath, QIcon, QPixmap
        )
        import pyaudio

        # QApplication must already exist on this (main) thread.
        app = QApplication.instance()
        if app is None:
            log.error("Settings: QApplication not ready — window skipped.")
            return

        # ── Themes ───────────────────────────
        THEMES = {
            "dark": {
                "bg"          : "#0d0d0d",
                "surface"     : "#141414",
                "surface2"    : "#1a1a1a",
                "border"      : "#252525",
                "text"        : "#f2f2f2",
                "text2"       : "#7a7a7a",
                "accent"      : "#569c12",
                "accent_dark" : "#3d7009",
                "blue"        : "#2D68C4",
                "red"         : "#920000",
                "input_bg"    : "#111111",
                "hover"       : "#202020",
                "card_bg"     : "#161616",
            },
            "light": {
                "bg"          : "#ffffff",
                "surface"     : "#ffffff",
                "surface2"    : "#f2f2f2",
                "border"      : "#e0e0e0",
                "text"        : "#0d0d0d",
                "text2"       : "#777777",
                "accent"      : "#569c12",
                "accent_dark" : "#3d7009",
                "blue"        : "#2D68C4",
                "red"         : "#920000",
                "input_bg"    : "#f8f8f8",
                "hover"       : "#ebebeb",
                "card_bg"     : "#f5f5f5",
            },
        }

        current_theme = ["dark"]

        def c(key):
            return THEMES[current_theme[0]][key]

        # ── Status dot ────────────────────────
        from PyQt6.QtWidgets import QWidget

        class StatusDot(QWidget):
            def __init__(self):
                super().__init__()
                self._on   = True
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
                # FIX [1]: clamp _pulse to [0.0, 1.0] BEFORE boundary check.
                # Previously _pulse could momentarily exceed 1.0, making
                # 150 + 105 * 1.002 = 255.21 → int 255 ... wait actually
                # int(255.21) = 255 which is fine, but _pulse = 1.002 meant
                # the >= 1.0 check fired a tick late, allowing values like
                # _pulse = 1.08 → alpha = int(150 + 105*1.08) = int(263.4) = 263 → crash.
                # Clamping first guarantees alpha is always in [150, 255].
                self._pulse = min(1.0, max(0.0, self._pulse + 0.08 * self._dir))
                if self._pulse >= 1.0:
                    self._dir = -1
                elif self._pulse <= 0.0:
                    self._dir = 1
                self.update()

            def paintEvent(self, _e):
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                col = QColor("#569c12") if self._on else QColor("#920000")
                # _pulse is clamped to [0,1] → alpha in [150, 255] — always safe
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

        stats = _load_stats()
        most_opened = "—"
        if stats.get("most_opened"):
            most_opened = max(stats["most_opened"], key=lambda k: stats["most_opened"][k])

        def apply_theme():
            win.setStyleSheet(f"""
                QWidget {{
                    background-color: {c('bg')};
                    color: {c('text')};
                    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                    font-size: 13px;
                }}
                QTabWidget::pane {{
                    border: 1px solid {c('border')};
                    border-radius: 8px;
                    background: {c('surface')};
                }}
                QTabBar::tab {{
                    background: {c('surface2')};
                    color: {c('text2')};
                    padding: 8px 20px;
                    border: none;
                    font-size: 12px;
                    font-weight: 500;
                    min-width: 80px;
                }}
                QTabBar::tab:selected {{
                    background: {c('accent')};
                    color: #ffffff;
                    font-weight: 700;
                }}
                QTabBar::tab:hover:!selected {{
                    background: {c('hover')};
                    color: {c('text')};
                }}
                QPushButton {{
                    background-color: {c('surface2')};
                    color: {c('text')};
                    border: 1px solid {c('border')};
                    padding: 7px 16px;
                    border-radius: 7px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {c('hover')};
                    border-color: {c('accent')};
                }}
                QPushButton#accent_btn {{
                    background-color: {c('accent')};
                    color: #ffffff;
                    border: none;
                    font-weight: 700;
                }}
                QPushButton#accent_btn:hover {{
                    background-color: {c('accent_dark')};
                }}
                QPushButton#danger_btn {{
                    background-color: transparent;
                    color: {c('red')};
                    border: 1px solid {c('red')};
                    padding: 2px 8px;
                    font-size: 12px;
                }}
                QPushButton#danger_btn:hover {{
                    background-color: {c('red')};
                    color: #ffffff;
                }}
                QLineEdit {{
                    background-color: {c('input_bg')};
                    border: 1px solid {c('border')};
                    border-radius: 6px;
                    padding: 7px 11px;
                    color: {c('text')};
                }}
                QLineEdit:focus {{
                    border-color: {c('accent')};
                }}
                QSlider::groove:horizontal {{
                    height: 4px;
                    background: {c('border')};
                    border-radius: 2px;
                }}
                QSlider::handle:horizontal {{
                    background: {c('accent')};
                    width: 16px;
                    height: 16px;
                    border-radius: 8px;
                    margin: -6px 0;
                }}
                QSlider::sub-page:horizontal {{
                    background: {c('accent')};
                    border-radius: 2px;
                }}
                QComboBox {{
                    background: {c('input_bg')};
                    border: 1px solid {c('border')};
                    border-radius: 6px;
                    padding: 6px 11px;
                    color: {c('text')};
                }}
                QComboBox QAbstractItemView {{
                    background: {c('surface2')};
                    color: {c('text')};
                    border: 1px solid {c('border')};
                    selection-background-color: {c('accent')};
                }}
                QScrollArea {{ border: none; background: transparent; }}
                QScrollBar:vertical {{
                    background: {c('surface2')};
                    width: 5px;
                    border-radius: 2px;
                }}
                QScrollBar::handle:vertical {{
                    background: {c('border')};
                    border-radius: 2px;
                    min-height: 20px;
                }}
                QCheckBox::indicator {{
                    width: 16px; height: 16px;
                    border-radius: 4px;
                    border: 1px solid {c('border')};
                    background: {c('input_bg')};
                }}
                QCheckBox::indicator:checked {{
                    background: {c('accent')};
                    border-color: {c('accent')};
                }}
                QTextEdit {{
                    background: {c('input_bg')};
                    border: 1px solid {c('border')};
                    border-radius: 6px;
                    color: {c('text')};
                    font-family: 'Consolas', monospace;
                    font-size: 12px;
                    padding: 8px;
                }}
                QListWidget {{
                    background: {c('input_bg')};
                    border: 1px solid {c('accent')};
                    border-radius: 6px;
                    color: {c('text')};
                    font-size: 12px;
                    padding: 2px;
                }}
                QListWidget::item:hover {{
                    background: {c('accent')};
                    color: #ffffff;
                    border-radius: 4px;
                }}
                QListWidget::item:selected {{
                    background: {c('accent')};
                    color: #ffffff;
                    border-radius: 4px;
                }}
            """)

        # ── Root layout ───────────────────────
        root = QVBoxLayout(win)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────
        header = QWidget()
        header.setFixedHeight(76)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 12, 20, 12)
        hl.addWidget(mic_logo)
        hl.addSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("ShowMe")
        title_lbl.setFont(QFont("Segoe UI Variable", 19, QFont.Weight.Bold))
        sub_lbl = QLabel("say it. it opens.  ·  v1.0")
        sub_lbl.setStyleSheet("color: #569c12; font-size: 11px; font-weight: 500;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        hl.addLayout(title_col)
        hl.addStretch()

        theme_combo = QComboBox()
        theme_combo.addItems(["Dark", "Light"])
        theme_combo.setFixedWidth(90)
        theme_combo.setFixedHeight(30)
        hl.addWidget(theme_combo)
        root.addWidget(header)

        # ── Status bar ────────────────────────
        status_bar = QWidget()
        status_bar.setFixedHeight(34)
        sl = QHBoxLayout(status_bar)
        sl.setContentsMargins(20, 0, 20, 0)
        sl.setSpacing(8)
        sl.addWidget(status_dot)
        status_text = QLabel("Listening")
        status_text.setStyleSheet("color: #2D68C4; font-size: 12px; font-weight: 600;")
        sl.addWidget(status_text)
        sl.addStretch()
        last_cmd_lbl = QLabel("Last: —")
        last_cmd_lbl.setStyleSheet("color: #666; font-size: 11px;")
        sl.addWidget(last_cmd_lbl)
        root.addWidget(status_bar)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        root.addWidget(div)

        # ── Tabs ──────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        root.addWidget(tabs)

        # ════════ TAB 1 — Dashboard ══════════
        dash = QWidget()
        dl = QVBoxLayout(dash)
        dl.setContentsMargins(20, 18, 20, 18)
        dl.setSpacing(12)

        def stat_card(value, label, color="#569c12"):
            card = QWidget()
            card.setFixedHeight(68)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 8, 14, 8)
            v = QLabel(str(value))
            v.setFont(QFont("Segoe UI Variable", 20, QFont.Weight.Bold))
            v.setStyleSheet(f"color: {color};")
            l2 = QLabel(label)
            l2.setStyleSheet("color: #666; font-size: 11px;")
            cl.addWidget(v)
            cl.addWidget(l2)
            return card

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        stats_row.addWidget(stat_card(stats.get("total", 0), "total commands", "#569c12"))
        stats_row.addWidget(stat_card(stats.get("today", 0), "today", "#2D68C4"))
        stats_row.addWidget(stat_card(most_opened, "most opened", "#888"))
        dl.addLayout(stats_row)

        ac = QWidget()
        ac.setFixedHeight(48)
        acl = QHBoxLayout(ac)
        acl.setContentsMargins(14, 0, 10, 0)
        ac_lbl = QLabel(f"  {len(app_dict)} apps indexed and ready")
        ac_lbl.setStyleSheet("color: #aaa; font-size: 13px;")
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        sc = QWidget()
        scl = QVBoxLayout(sc)
        scl.setSpacing(1)
        scl.setContentsMargins(0, 0, 0, 0)

        all_names = sorted(app_dict.keys())

        def populate(filter_text=""):
            for i in reversed(range(scl.count())):
                w = scl.itemAt(i).widget()
                if w:
                    w.deleteLater()
            names = [n for n in all_names if filter_text.lower() in n.lower()]
            for name in names[:200]:
                row = QWidget()
                row.setFixedHeight(28)
                rl2 = QHBoxLayout(row)
                rl2.setContentsMargins(10, 0, 10, 0)
                dot2 = QLabel("·")
                dot2.setStyleSheet("color: #569c12; font-size: 14px;")
                lbl2 = QLabel(name)
                lbl2.setStyleSheet("color: #bbb; font-size: 12px;")
                rl2.addWidget(dot2)
                rl2.addWidget(lbl2)
                rl2.addStretch()
                scl.addWidget(row)

        populate()
        search.textChanged.connect(populate)
        scroll.setWidget(sc)
        scroll.setFixedHeight(180)
        dl.addWidget(scroll)
        dl.addStretch()
        tabs.addTab(dash, "Dashboard")

        # ════════ TAB 2 — Commands ════════════
        cmd_tab = QWidget()
        ctl = QVBoxLayout(cmd_tab)
        ctl.setContentsMargins(20, 18, 20, 18)
        ctl.setSpacing(10)

        ct = QLabel("Custom Voice Commands")
        ct.setFont(QFont("Segoe UI Variable", 13, QFont.Weight.Bold))
        ctl.addWidget(ct)

        cs = QLabel('Map any phrase → app. Type phrase + pick app from suggestions.')
        cs.setStyleSheet("color: #888; font-size: 12px;")
        cs.setWordWrap(True)
        ctl.addWidget(cs)

        add_row = QHBoxLayout()
        phrase_input = QLineEdit()
        phrase_input.setPlaceholderText('Voice phrase  e.g. "exploded"')
        app_input = QLineEdit()
        app_input.setPlaceholderText('App name — type to search')

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
                row2.setFixedHeight(34)
                rl3 = QHBoxLayout(row2)
                rl3.setContentsMargins(12, 0, 8, 0)
                p_lbl = QLabel(f'"{phrase}"')
                p_lbl.setStyleSheet("color: #569c12; font-size: 12px;")
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #444;")
                t_lbl = QLabel(target)
                t_lbl.setStyleSheet("color: #aaa; font-size: 12px;")
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
        ctl.addWidget(cmd_scroll)
        tabs.addTab(cmd_tab, "Commands")

        # ════════ TAB 3 — Settings ════════════
        settings_tab = QWidget()
        stl = QVBoxLayout(settings_tab)
        stl.setContentsMargins(20, 18, 20, 18)
        stl.setSpacing(16)

        def section_lbl(text):
            l3 = QLabel(text)
            l3.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Bold))
            l3.setStyleSheet("color: #569c12; letter-spacing: 1.5px;")
            return l3

        stl.addWidget(section_lbl("MATCH SENSITIVITY"))
        sens_row = QHBoxLayout()
        sens_lbl = QLabel("Threshold")
        sens_val = QLabel("85")
        sens_val.setFixedWidth(28)
        sens_val.setStyleSheet("color: #569c12; font-weight: bold;")
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
        hint = QLabel("Lower = more lenient  ·  Higher = stricter matching")
        hint.setStyleSheet("color: #555; font-size: 11px;")
        stl.addWidget(hint)

        stl.addWidget(section_lbl("MICROPHONE"))
        mic_combo = QComboBox()
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
                    script = os.path.join(
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

        # ════════ TAB 4 — Test Mic ════════════
        test_tab = QWidget()
        ttl = QVBoxLayout(test_tab)
        ttl.setContentsMargins(20, 18, 20, 18)
        ttl.setSpacing(10)

        tt = QLabel("Microphone Test")
        tt.setFont(QFont("Segoe UI Variable", 13, QFont.Weight.Bold))
        ttl.addWidget(tt)
        ts = QLabel("Speak after pressing Start. See exactly what ShowMe hears.")
        ts.setStyleSheet("color: #888; font-size: 12px;")
        ttl.addWidget(ts)

        test_out = QTextEdit()
        test_out.setReadOnly(True)
        test_out.setPlaceholderText("Transcript will appear here...")
        test_out.setFixedHeight(200)
        ttl.addWidget(test_out)

        tbr = QHBoxLayout()
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

                model = vosk.Model(model_dir)
                rec = vosk.KaldiRecognizer(model, 16000)
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
                        text = result.get("text", "").strip()
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

        # ── Bottom bar ────────────────────────
        bottom = QWidget()
        bottom.setFixedHeight(42)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(20, 0, 20, 0)
        footer = QLabel("ShowMe v1.0  ·  open source  ·  github.com/thattimelessman")
        footer.setStyleSheet("color: #333; font-size: 10px;")
        bl.addWidget(footer)
        bl.addStretch()
        rescan_btn = QPushButton("Rescan Apps")
        rescan_btn.setFixedHeight(28)
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(28)
        bl.addWidget(rescan_btn)
        bl.addWidget(close_btn)
        root.addWidget(bottom)

        # ── Callbacks ─────────────────────────
        def on_theme(idx):
            current_theme[0] = "dark" if idx == 0 else "light"
            apply_theme()

        theme_combo.currentIndexChanged.connect(on_theme)
        rescan_btn.clicked.connect(lambda: (on_rescan_callback(), win.close()))
        rescan2.clicked.connect(lambda: (on_rescan_callback(), win.close()))
        close_btn.clicked.connect(win.close)

        def poll_status():
            if listener_status_queue:
                try:
                    while True:
                        msg = listener_status_queue.get_nowait()
                        if msg == "Listening":
                            status_dot.set_listening(True)
                            mic_logo.setPixmap(QPixmap(_icon_path).scaled(
                                52, 52,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))
                            win.setWindowIcon(QIcon(_icon_path))
                            status_text.setText("Listening")
                            status_text.setStyleSheet(
                                "color: #2D68C4; font-size: 12px; font-weight: 600;"
                            )
                        elif msg == "Stopped":
                            status_dot.set_listening(False)
                            mic_logo.setPixmap(QPixmap(_icon_path_r).scaled(
                                52, 52,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))
                            win.setWindowIcon(QIcon(_icon_path_r))
                            status_text.setText("Paused")
                            status_text.setStyleSheet(
                                "color: #920000; font-size: 12px; font-weight: 600;"
                            )
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

        # FIX [3]: Local QEventLoop tied to this window's lifetime.
        # When the window is closed/destroyed, loop.quit() fires and
        # _show_window returns — QApplication stays alive on the main
        # thread, ready for the next open. No more reopen crash.
        loop = QEventLoop()
        win.finished.connect(loop.quit)  # QDialog.finished fires on X or Close
        loop.exec()

    except Exception as e:
        log.error("Settings window error: %s", e)