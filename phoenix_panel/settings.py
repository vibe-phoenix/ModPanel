# -*- coding: utf-8 -*-
"""Settings dialog for PhoenixPanel — modern redesign."""

from __future__ import annotations

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from . import theme as _theme

# ── Palette ───────────────────────────────────────────────────────────────────
# Deeper, richer dark theme with more contrast between layers (background /
# sidebar / surface / raised cards) so the UI reads as distinct depth levels
# rather than one flat slab. All keys that existed before are kept (many
# stylesheets elsewhere in this file do `.format(**_C)`), only values changed
# plus a handful of new tokens added for the sidebar nav / cards / accents.
_C = {
    "bg":        "#0e1016",
    "surface":   "#151824",
    "raise_":    "#1b1f2d",
    "border":    "#262b3d",
    "focus":     "#2f8fef",
    "text":      "#f5f6fc",
    "dim":       "#adb4d1",
    "hint":      "#7d84a3",
    "input":     "#0a0c12",
    "btn":       "#1b1f2d",
    "hover":     "#242a3d",
    "accent":    "#2f8fef",
    "green":     "#33b874",
    "green_h":   "#3fd287",
    "red":       "#e2495f",
    "red_h":     "#f25a70",
    "red_dim":   "#ff9fae",

    # New tokens — safe to add, existing .format(**_C) calls simply ignore
    # any keys they don't reference.
    "bg2":        "#101320",
    "sidebar":    "#0d0f18",
    "sidebar_sel":"#1a2c47",
    "card":       "#171b28",
    "border2":    "#323852",
    "accent_h":   "#5aa8ff",
    "accent_dim": "#1f3f66",
    "shadow":     "#000000",
}

# ── Shared stylesheets ────────────────────────────────────────────────────────
_SS_INPUT = """
QLineEdit, QTextEdit {{
    background: {input};
    color: {text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px 8px;
    font-family: Consolas, "Courier New", monospace;
    font-size: 11px;
    selection-background-color: {accent_dim};
}}
QLineEdit:focus, QTextEdit:focus {{ border-color: {focus}; }}
QLineEdit:hover, QTextEdit:hover {{ border-color: {border2}; }}
""".format(**_C)

_SS_SPIN = """
QSpinBox, QDoubleSpinBox {{
    background: {input};
    color: {text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px 6px;
    font-size: 11px;
    min-width: 60px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {focus}; }}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: {btn};  border: none;  width: 16px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {hover};
}}
""".format(**_C)

_SS_COMBO = """
QComboBox {{
    background: {input};
    color: {text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    min-width: 90px;
}}
QComboBox:hover {{ border-color: {border2}; }}
QComboBox:focus {{ border-color: {focus}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {surface};
    color: {text};
    border: 1px solid {border2};
    border-radius: 6px;
    selection-background-color: {accent_dim};
    outline: none;
    padding: 2px;
}}
""".format(**_C)

_SS_CHECK = """
QCheckBox {{ color: {dim}; font-size: 11px; spacing: 7px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {border2}; border-radius: 4px; background: {input};
}}
QCheckBox::indicator:hover {{ border-color: {focus}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
""".format(**_C)

_SS_SLIDER = """
QSlider::groove:horizontal {{
    height:4px; background:{input}; border-radius:2px;
}}
QSlider::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {accent_h}, stop:1 {accent});
    width:14px; height:14px;
    margin:-5px 0; border-radius:7px;
    border: 1px solid {bg};
}}
QSlider::handle:horizontal:hover {{ background:{accent_h}; }}
QSlider::sub-page:horizontal {{ background:{accent}; border-radius:2px; }}
QSlider::add-page:horizontal {{ background:{border}; border-radius:2px; }}
""".format(**_C)


# ── Tiny helpers ──────────────────────────────────────────────────────────────
def _lbl(text, color=None, size=11, bold=False):
    w = QtWidgets.QLabel(text)
    w.setWordWrap(True)
    _theme.set_qss(w, "background:transparent; color:{}; font-size:{}px;{}".format(
            color or _C["dim"], size, " font-weight:600;" if bold else ""
        ))
    return w


def _rule():
    f = QtWidgets.QFrame()
    f.setFrameShape(QtWidgets.QFrame.HLine)
    f.setFixedHeight(1)
    _theme.set_qss(f, "background:{border}; border:none; margin: 4px 0;".format(**_C))
    return f


def _row(*widgets, spacing=8):
    """Pack widgets into a transparent HBox."""
    w = QtWidgets.QWidget()
    _theme.set_qss(w, "background:transparent;")
    h = QtWidgets.QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(spacing)
    for x in widgets:
        if isinstance(x, int):
            h.addSpacing(x)
        elif x == "stretch":
            h.addStretch(1)
        else:
            h.addWidget(x)
    return w


def _field(label_text, widget, label_w=100):
    """Right-aligned label + widget."""
    lbl = _lbl(label_text)
    lbl.setFixedWidth(label_w)
    lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    return _row(lbl, widget)


def _section_header(text, parent_lay):
    """Add a section header with a small accent tick, to parent_lay."""
    row = QtWidgets.QHBoxLayout()
    row.setContentsMargins(0, 10, 0, 4)
    row.setSpacing(6)
    tick = QtWidgets.QFrame()
    tick.setFixedSize(3, 12)
    _theme.set_qss(tick, "background:{accent}; border-radius:1px;".format(**_C))
    row.addWidget(tick)
    hdr = _lbl(text, _C["dim"], 10, bold=True)
    row.addWidget(hdr)
    row.addStretch(1)
    parent_lay.addLayout(row)


def _card(inner_layout=None):
    """A subtly raised container — used to group related controls visually
    instead of everything sitting flat against the page background."""
    w = QtWidgets.QFrame()
    _theme.set_qss(w, """
    QFrame {{
        background: {card};
        border: 1px solid {border};
        border-radius: 8px;
    }}
    """.format(**_C))
    lay = inner_layout or QtWidgets.QVBoxLayout(w)
    if inner_layout is None:
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
    return w, lay


class _ColorButton(QtWidgets.QPushButton):
    colorChanged = QtCore.Signal(str)

    def __init__(self, colour="#ffffff", parent=None):
        super(_ColorButton, self).__init__(parent)
        self._colour = "#ffffff"
        self.setFixedHeight(28)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.clicked.connect(self._choose)
        self.set_colour(colour, emit=False)

    def colour(self):
        return self._colour

    def set_colour(self, colour, emit=False):
        q = QtGui.QColor(colour)
        if not q.isValid():
            return
        self._colour = q.name().lower()
        text = "#ffffff" if q.lightness() < 128 else "#111111"
        self.setText(self._colour.upper())
        # Swatch background is the real chosen colour, so it is never passed
        # through the style translation; only the chrome around it is.
        self.setStyleSheet("""
        QPushButton {{ background:{bg}; color:{text}; border:1px solid {border};
                       border-radius:{radius}px; font-size:10px; font-weight:600; }}
        QPushButton:hover {{ border:2px solid {accent}; }}
        """.format(bg=self._colour, text=text, border=_theme.col(_C["border2"]),
                   accent=_theme.col(_C["accent_h"]), radius=_theme.radius(6)))
        if emit:
            self.colorChanged.emit(self._colour)

    def _choose(self):
        chosen = QtWidgets.QColorDialog.getColor(QtGui.QColor(self._colour), self,
                                                 "Choose Color")
        if chosen.isValid():
            self.set_colour(chosen.name(), emit=True)


# ── Main dialog ───────────────────────────────────────────────────────────────
class PhoenixPanelSettings(QtWidgets.QDialog):

    settingsChanged = QtCore.Signal()

    def __init__(self, parent, panel):
        super(PhoenixPanelSettings, self).__init__(parent)
        from .utils import install_wheel_guard
        install_wheel_guard(self)

        self.panel     = panel
        self._drag_pos = None

        self.setWindowTitle("ModPanel Settings")
        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(560, 480)
        self.resize(620, 580)

        self._ws_list = None
        self._loaded_tabs = set()
        self._look_draft = self.panel.export_look_settings()

        # ── Shell ──────────────────────────────────────────────────────
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = QtWidgets.QWidget()
        shell.setObjectName("Shell")
        _theme.set_qss(shell, """
        QWidget#Shell {{
            background: {bg};
            border-radius: 10px;
            border: 1px solid {border2};
        }}
        """.format(**_C))
        outer.addWidget(shell)

        sl = QtWidgets.QVBoxLayout(shell)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        sl.addWidget(self._build_titlebar())

        # ── Body: sidebar nav + stacked pages ───────────────────────────
        body = QtWidgets.QWidget()
        _theme.set_qss(body, "background: transparent;")
        body_lay = QtWidgets.QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self._tab_names = ["Layout", "Buttons", "Title", "Workspaces",
                           "Look", "Data", "Free Stuff", "Credits"]
        self._tab_builders = [
            self._tab_layout, self._tab_buttons, self._tab_title, self._tab_workspaces,
            self._tab_look, self._tab_data, self._tab_free_stuff, self._tab_credits
        ]

        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setFixedWidth(148)
        self.nav_list.setFrameShape(QtWidgets.QFrame.NoFrame)
        _theme.set_qss(self.nav_list, """
        QListWidget {{
            background: {sidebar};
            border: none;
            border-right: 1px solid {border};
            padding: 8px 0;
            outline: none;
        }}
        QListWidget::item {{
            color: {dim};
            padding: 9px 8px 9px 16px;
            margin: 1px 6px;
            border-radius: 6px;
            font-size: 11px;
        }}
        QListWidget::item:hover {{ background: {hover}; color: {text}; }}
        QListWidget::item:selected {{
            background: {sidebar_sel}; color: {text}; font-weight: 600;
        }}
        """.format(**_C))
        for name in self._tab_names:
            self.nav_list.addItem(QtWidgets.QListWidgetItem(name))
        body_lay.addWidget(self.nav_list)

        self.stack = QtWidgets.QStackedWidget()
        _theme.set_qss(self.stack, "background: transparent;")
        for _ in self._tab_names:
            placeholder = QtWidgets.QWidget()
            _theme.set_qss(placeholder, "background:transparent;")
            self.stack.addWidget(placeholder)
        body_lay.addWidget(self.stack, 1)

        # Floating "Apply" button — only shown over the Look tab. Parented
        # directly to the stack (not placed in any layout) so it floats
        # above the scrollable tab content at a fixed top-right position,
        # independent of scroll position, and applies the in-progress Look
        # draft straight to the real panel without closing this dialog.
        self._look_tab_index = self._tab_names.index("Look")
        self._look_apply_btn = QtWidgets.QPushButton("Apply", self.stack)
        self._look_apply_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._look_apply_btn.setFixedHeight(30)
        self._look_apply_btn.setMinimumWidth(74)
        _theme.set_qss(self._look_apply_btn, """
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {accent_h}, stop:1 {accent});
            color:#fff; border:none;
            border-radius:15px; font-size:11px; font-weight:600;
            padding: 0 16px;
        }}
        QPushButton:hover {{ background: {accent_h}; }}
        QPushButton:pressed {{ background: {accent_dim}; }}
        """.format(**_C))
        self._look_apply_btn.clicked.connect(self._apply_look_now)
        self._look_apply_btn.hide()

        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        self.nav_list.setCurrentRow(0)
        self._ensure_tab_loaded(0)
        self.stack.setCurrentIndex(0)

        sl.addWidget(body, 1)

        # ── Apply bar ──────────────────────────────────────────────────
        sl.addWidget(self._build_applybar())

        self._reposition_look_apply_btn()

    def _on_nav_changed(self, index):
        self._ensure_tab_loaded(index)
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)
        if hasattr(self, "_look_apply_btn"):
            self._look_apply_btn.setVisible(index == self._look_tab_index)
            self._reposition_look_apply_btn()

    def _reposition_look_apply_btn(self):
        if not hasattr(self, "_look_apply_btn"):
            return
        margin = 12
        x = self.stack.width() - self._look_apply_btn.width() - margin
        self._look_apply_btn.move(max(0, x), margin)
        self._look_apply_btn.raise_()

    def resizeEvent(self, event):
        super(PhoenixPanelSettings, self).resizeEvent(event)
        self._reposition_look_apply_btn()

    def _apply_look_now(self):
        """Push the in-progress Look draft straight onto the real panel —
        deliberately does NOT close this dialog, unlike the main Save
        Changes button, so colors/spacing can be iterated on and checked
        against the live panel repeatedly."""
        if not isinstance(getattr(self, "_look_draft", None), dict):
            return
        try:
            self.panel.apply_look_settings(self._look_draft, save=True, refresh=True)
        except Exception as e:
            try:
                import maya.cmds as cmds
                cmds.warning("ModPanel: could not apply look: {}".format(e))
            except Exception:
                pass

    def _ensure_tab_loaded(self, index):
        """Build expensive settings pages only when the user opens them."""
        if index < 0 or index >= len(self._tab_builders):
            return
        if index in self._loaded_tabs:
            return

        page = self._tab_builders[index]()
        old = self.stack.widget(index)
        self.stack.insertWidget(index, page)
        self._loaded_tabs.add(index)
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()

    @staticmethod
    def _set_combo_text(combo, text):
        idx = combo.findText(text or "")
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def refresh_from_panel(self):
        """Refresh already-created controls before reusing the cached dialog."""
        p = self.panel
        if 0 in self._loaded_tabs:
            self.panel_scale_spin.blockSignals(True)
            self.panel_scale_spin.setValue(getattr(p, "panel_scale", 1.0))
            self.panel_scale_spin.blockSignals(False)
            self.panel_scale_slider.blockSignals(True)
            self.panel_scale_slider.setValue(int(round(getattr(p, "panel_scale", 1.0) * 10)))
            self.panel_scale_slider.blockSignals(False)
            self.cols_spin.setValue(p.cols)
            self.scale_spin.setValue(p.button_scale)
            self.pad_spin.setValue(p.padding)
            self.align_combo.setCurrentIndex(p.quick_alignment)
            self.grid_full_row_align_combo.setCurrentIndex(
                getattr(p, "grid_full_row_alignment", 1))
            self.grid_row_align_combo.setCurrentIndex(
                getattr(p, "grid_row_alignment", 1))
            self.btn_gap_slider.setValue(getattr(p, "quick_button_gap", 4))
            self.hot_button_icon_scale_slider.setValue(
                int(round(getattr(p, "hot_button_icon_scale", 1.0) * 100)))
            self.pie_icon_scale_slider.setValue(
                int(round(getattr(p, "pie_icon_scale", 1.0) * 100)))
            self.hot_pie_icon_scale_slider.setValue(
                int(round(getattr(p, "hot_pie_icon_scale", 1.0) * 100)))
            self.pie_hold_delay_slider.setValue(int(getattr(p, "pie_hold_delay_ms", 100)))
            self.pie_dim_check.setChecked(getattr(p, "pie_dim_enabled", True))
            self.pie_dim_mode_combo.setCurrentIndex(
                1 if getattr(p, "pie_dim_mode", "panel") == "screen" else 0)
            self.pie_dim_delay_slider.setValue(int(getattr(p, "pie_dim_delay_ms", 150)))
            self.pie_dim_fade_slider.setValue(int(getattr(p, "pie_dim_fade_ms", 200)))
            self.pie_dim_opacity_slider.setValue(int(getattr(p, "pie_dim_opacity", 55)))
            self.pie_angle_slider.setValue(int(round(getattr(p, "pie_start_angle", -90.0))))
            self._set_pie_dim_controls_enabled(getattr(p, "pie_dim_enabled", True))
            self.close_on_click_check.setChecked(getattr(p, "close_on_click", True))
            self.search_always_on_check.setChecked(getattr(p, "search_always_on", False))
            self.recent_commands_check.setChecked(
                getattr(p, "recent_commands_enabled", True))
            self.node_detection_check.setChecked(
                getattr(p, "node_detection_enabled", True))

        if 1 in self._loaded_tabs:
            count = max(0, min(10, int(getattr(p, "quick_button_count", 0))))
            self.hot_button_count_slider.setValue(count)
            self._quick_icons = []
            self._quick_rc_icons = []
            for i in range(10):
                data = p.custom_buttons[i]
                rc = p.quick_button_rc[i]
                self.quick_name_edits[i].setText(
                    (data.get("name") or "BTN{}".format(i + 1))[:6])
                self.quick_tooltip_edits[i].setText(data.get("tooltip", ""))
                self.quick_type_boxes[i].setCurrentIndex(
                    1 if (data.get("type", "mel") or "mel").lower() == "python" else 0)
                self.quick_code_edits[i].setPlainText(data.get("code", ""))
                self.quick_close_override_checks[i].setChecked(
                    bool(data.get("invert_close_on_click", False)))
                self.quick_rc_name_edits[i].setText(rc.get("name", ""))
                self.quick_rc_type_boxes[i].setCurrentIndex(
                    0 if (rc.get("type", "python") or "python").lower() == "python" else 1)
                self.quick_rc_code_edits[i].setPlainText(rc.get("code", ""))
                self._quick_icons.append(data.get("icon", ""))
                self._quick_rc_icons.append(rc.get("icon", ""))
            self._reload_icon_previews()
            self._refresh_vis_states()

        if 2 in self._loaded_tabs:
            self.panel_title_edit.setText(getattr(p, "panel_title", "ModPanel") or "ModPanel")
            self.title_click_edit.setPlainText(getattr(p, "title_click_code", "") or "")
            self.title_click_type_box.setCurrentIndex(
                0 if (getattr(p, "title_click_type", "python") or "python").lower() == "python" else 1)
            self.title_click_tooltip_edit.setText(getattr(p, "title_click_tooltip", "") or "")
            self.title_right_click_edit.setPlainText(
                getattr(p, "title_right_click_code", "") or "")
            self.title_right_click_type_box.setCurrentIndex(
                0 if (getattr(p, "title_right_click_type", "python") or "python").lower() == "python" else 1)
            self.title_right_click_tooltip_edit.setText(
                getattr(p, "title_right_click_tooltip", "") or "")
            self.title_double_click_edit.setPlainText(
                getattr(p, "title_double_click_code", "") or "")
            self.title_double_click_type_box.setCurrentIndex(
                0 if (getattr(p, "title_double_click_type", "python") or "python").lower() == "python" else 1)
            self.title_double_click_tooltip_edit.setText(
                getattr(p, "title_double_click_tooltip", "") or "")

        if 3 in self._loaded_tabs:
            cyc = getattr(p, "workspace_cycle", ["General", "UV Editing"])
            self._set_combo_text(self.ws_a_combo, cyc[0])
            self._set_combo_text(self.ws_b_combo, cyc[1])
            self._set_combo_text(self.uv_ws_combo, getattr(p, "uv_tab_workspace", "UV Editing"))

        if 4 in self._loaded_tabs:
            self._look_draft = p.export_look_settings()
            self._sync_look_controls()
            self._refresh_ui_style_buttons()

    # ── Title bar ──────────────────────────────────────────────────────────────
    def _build_titlebar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("TBar")
        bar.setFixedHeight(44)
        bar.setCursor(QtGui.QCursor(QtCore.Qt.SizeAllCursor))
        _theme.set_qss(bar, """
        QWidget#TBar {{
            background: {surface};
            border-bottom: 1px solid {border};
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        }}
        """.format(**_C))
        bar.mousePressEvent   = self._tp
        bar.mouseMoveEvent    = self._tm
        bar.mouseReleaseEvent = lambda e: setattr(self, "_drag_pos", None)

        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 10, 0)
        h.setSpacing(9)

        dot = QtWidgets.QFrame()
        dot.setFixedSize(8, 8)
        _theme.set_qss(dot, """
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {accent}, stop:1 {accent_h});
        border-radius: 4px;
        """.format(**_C))
        h.addWidget(dot)

        title_col = QtWidgets.QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)
        title_col.addWidget(_lbl("ModPanel", _C["text"], 12, bold=True))
        title_col.addWidget(_lbl("Settings", _C["hint"], 9))
        h.addLayout(title_col)
        h.addStretch(1)

        x = QtWidgets.QPushButton("✕")
        x.setFixedSize(24, 24)
        x.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        _theme.set_qss(x, """
        QPushButton {{
            background: transparent; color:{dim};
            border-radius:6px; font-size:11px;
        }}
        QPushButton:hover {{ background:{red}; color:#fff; }}
        """.format(**_C))
        x.clicked.connect(self.close)
        h.addWidget(x)
        return bar

    def _tp(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            try:    self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            except: self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _tm(self, e):
        if self._drag_pos and e.buttons() & QtCore.Qt.LeftButton:
            try:    self.move(e.globalPos() - self._drag_pos)
            except: self.move(e.globalPosition().toPoint() - self._drag_pos)

    # ── Apply bar ─────────────────────────────────────────────────────────────
    def _build_applybar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("ABar")
        _theme.set_qss(bar, """
        QWidget#ABar {{
            background: {surface};
            border-top: 1px solid {border};
            border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;
        }}
        """.format(**_C))
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(16, 9, 16, 11)
        h.setSpacing(8)

        hint = _lbl("Changes are applied when Save Changes is pressed.",
                     _C["hint"], 9)
        h.addWidget(hint)
        h.addStretch(1)

        btn = QtWidgets.QPushButton("Save Changes")
        btn.setFixedHeight(30)
        btn.setMinimumWidth(120)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        _theme.set_qss(btn, """
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {accent_h}, stop:1 {accent});
            color:#fff; border:none;
            border-radius:6px; font-size:11px; font-weight:600;
            padding: 0 16px;
        }}
        QPushButton:hover {{ background: {accent_h}; }}
        QPushButton:pressed {{ background: {accent_dim}; }}
        """.format(**_C))
        btn.clicked.connect(self.apply_changes)
        h.addWidget(btn)
        return bar

    # ── Scrollable page factory ───────────────────────────────────────────────
    @staticmethod
    def _page():
        page = QtWidgets.QWidget()
        _theme.set_qss(page, "background:transparent;")
        pl = QtWidgets.QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        _theme.set_qss(scroll, """
        QScrollArea {{ background:transparent; border:none; }}
        QScrollArea > QWidget > QWidget {{ background:transparent; }}
        QScrollBar:vertical {{
            background:transparent; width:8px; margin:2px;
        }}
        QScrollBar::handle:vertical {{
            background:{border2}; border-radius:3px; min-height:24px;
        }}
        QScrollBar::handle:vertical:hover {{ background:{hint}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """.format(**_C))

        inner = QtWidgets.QWidget()
        _theme.set_qss(inner, "background:transparent;")
        il = QtWidgets.QVBoxLayout(inner)
        il.setContentsMargins(20, 18, 20, 18)
        il.setSpacing(7)
        scroll.setWidget(inner)
        pl.addWidget(scroll)
        return page, il

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Layout
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_layout(self):
        page, lay = self._page()
        lay.setSpacing(12)
        p = self.panel

        # ── Panel scale ──
        panel_scale_card, panel_scale_lay = _card()
        _section_header("PANEL SCALE", panel_scale_lay)
        panel_scale_lay.addWidget(_lbl(
            "Scales the whole panel — buttons, hot buttons, title bar, "
            "everything — up to 10x.", _C["hint"], 10))

        scale_row = QtWidgets.QHBoxLayout()
        scale_row.setSpacing(8)
        self.panel_scale_spin = QtWidgets.QDoubleSpinBox()
        self.panel_scale_spin.setRange(0.5, 10.0)
        self.panel_scale_spin.setSingleStep(0.1)
        self.panel_scale_spin.setDecimals(2)
        self.panel_scale_spin.setSuffix("x")
        self.panel_scale_spin.setValue(getattr(p, "panel_scale", 1.0))
        _theme.set_qss(self.panel_scale_spin, _SS_SPIN)
        self.panel_scale_spin.setFixedWidth(80)
        scale_row.addWidget(self.panel_scale_spin)

        self.panel_scale_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.panel_scale_slider.setRange(5, 100)   # represents 0.5x .. 10.0x
        self.panel_scale_slider.setValue(int(round(getattr(p, "panel_scale", 1.0) * 10)))
        _theme.set_qss(self.panel_scale_slider, _SS_SLIDER)
        scale_row.addWidget(self.panel_scale_slider, 1)
        panel_scale_lay.addLayout(scale_row)

        self.panel_scale_spin.valueChanged.connect(self._on_panel_scale_spin_changed)
        self.panel_scale_slider.valueChanged.connect(self._on_panel_scale_slider_changed)

        lay.addWidget(panel_scale_card)

        # ── Grid ──
        grid_card, grid_lay = _card()
        _section_header("GRID", grid_lay)

        self.cols_spin = QtWidgets.QSpinBox()
        self.cols_spin.setRange(1, 20)
        self.cols_spin.setValue(p.cols)
        _theme.set_qss(self.cols_spin, _SS_SPIN)
        self.cols_spin.setToolTip("Columns per row — rows are calculated automatically from button count")
        grid_lay.addWidget(_field("Columns", self.cols_spin))

        self.scale_spin = QtWidgets.QDoubleSpinBox()
        self.scale_spin.setRange(0.4, 3.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setValue(p.button_scale)
        _theme.set_qss(self.scale_spin, _SS_SPIN)
        grid_lay.addWidget(_field("Button Scale", self.scale_spin))

        self.pad_spin = QtWidgets.QSpinBox()
        self.pad_spin.setRange(0, 50)
        self.pad_spin.setValue(p.padding)
        _theme.set_qss(self.pad_spin, _SS_SPIN)
        self.pad_spin.setSuffix(" px")
        self.pad_spin.valueChanged.connect(self._sync_layout_spacing_to_look)
        grid_lay.addWidget(_field("Gap", self.pad_spin))
        lay.addWidget(grid_card)

        # ── Alignment ──
        align_card, align_lay = _card()
        _section_header("ALIGNMENT", align_lay)

        self.align_combo = QtWidgets.QComboBox()
        self.align_combo.addItems(["Left", "Center", "Right"])
        self.align_combo.setCurrentIndex(p.quick_alignment)
        _theme.set_qss(self.align_combo, _SS_COMBO)
        align_lay.addWidget(_field("Hot Buttons", self.align_combo))

        self.grid_full_row_align_combo = QtWidgets.QComboBox()
        self.grid_full_row_align_combo.addItems(["Left", "Center", "Right"])
        self.grid_full_row_align_combo.setCurrentIndex(getattr(p, "grid_full_row_alignment", 1))
        _theme.set_qss(self.grid_full_row_align_combo, _SS_COMBO)
        align_lay.addWidget(_field("Full Rows", self.grid_full_row_align_combo))

        self.grid_row_align_combo = QtWidgets.QComboBox()
        self.grid_row_align_combo.addItems(["Left", "Center", "Right"])
        self.grid_row_align_combo.setCurrentIndex(getattr(p, "grid_row_alignment", 1))
        _theme.set_qss(self.grid_row_align_combo, _SS_COMBO)
        align_lay.addWidget(_field("Last Row", self.grid_row_align_combo))
        lay.addWidget(align_card)

        # ── Hot Buttons ──
        hot_card, hot_lay = _card()
        _section_header("HOT BUTTONS", hot_lay)
        hot_lay.addWidget(_lbl("Spacing between the 10 icon buttons in the title bar.", _C["hint"], 10))

        gap_row = QtWidgets.QHBoxLayout()
        gap_row.setSpacing(8)
        self.btn_gap_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.btn_gap_slider.setRange(0, 20)
        self.btn_gap_slider.setValue(getattr(p, "quick_button_gap", 4))
        _theme.set_qss(self.btn_gap_slider, _SS_SLIDER)
        self.btn_gap_spin = self._make_value_spin(0, 20, getattr(p, "quick_button_gap", 4), " px")
        self._wire_slider_spin(self.btn_gap_slider, self.btn_gap_spin, self._on_gap_changed)
        gap_row.addWidget(self.btn_gap_slider, 1)
        gap_row.addWidget(self.btn_gap_spin)
        hot_lay.addLayout(gap_row)

        hot_lay.addWidget(_lbl(
            "Icon scale for the 10 hot buttons themselves — grows the buttons, "
            "the title bar's height, and their own pie menus together.",
            _C["hint"], 10))

        hot_scale_row = QtWidgets.QHBoxLayout()
        hot_scale_row.setSpacing(8)
        self.hot_button_icon_scale_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.hot_button_icon_scale_slider.setRange(50, 300)
        self.hot_button_icon_scale_slider.setValue(
            int(round(getattr(p, "hot_button_icon_scale", 1.0) * 100)))
        _theme.set_qss(self.hot_button_icon_scale_slider, _SS_SLIDER)
        self.hot_button_icon_scale_spin = self._make_value_spin(
            50, 300, self.hot_button_icon_scale_slider.value(), "%")
        self._wire_slider_spin(self.hot_button_icon_scale_slider, self.hot_button_icon_scale_spin,
                                self._on_hot_button_icon_scale_changed)
        hot_scale_row.addWidget(self.hot_button_icon_scale_slider, 1)
        hot_scale_row.addWidget(self.hot_button_icon_scale_spin)
        hot_lay.addLayout(hot_scale_row)

        reorder_row = QtWidgets.QHBoxLayout()
        reorder_hot_btn = QtWidgets.QPushButton("Reorder Hot Buttons...")
        reorder_hot_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        _theme.set_qss(reorder_hot_btn, self._pick_btn_ss())
        reorder_hot_btn.clicked.connect(self._open_hot_button_reorder)
        reorder_row.addWidget(reorder_hot_btn)
        reorder_row.addStretch(1)
        hot_lay.addLayout(reorder_row)
        lay.addWidget(hot_card)

        # ── Pie menu ──
        pie_card, pie_lay = _card()
        _section_header("PIE MENU", pie_lay)
        pie_lay.addWidget(_lbl(
            "Size of the icon and its box in each pie-menu item — panel buttons.",
            _C["hint"], 10))

        pie_scale_row = QtWidgets.QHBoxLayout()
        pie_scale_row.setSpacing(8)
        self.pie_icon_scale_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pie_icon_scale_slider.setRange(50, 150)
        self.pie_icon_scale_slider.setValue(
            int(round(getattr(p, "pie_icon_scale", 1.0) * 100)))
        _theme.set_qss(self.pie_icon_scale_slider, _SS_SLIDER)
        self.pie_icon_scale_spin = self._make_value_spin(
            50, 150, self.pie_icon_scale_slider.value(), "%")
        self._wire_slider_spin(self.pie_icon_scale_slider, self.pie_icon_scale_spin,
                                self._on_pie_icon_scale_changed)
        pie_scale_row.addWidget(self.pie_icon_scale_slider, 1)
        pie_scale_row.addWidget(self.pie_icon_scale_spin)
        pie_lay.addLayout(pie_scale_row)

        pie_lay.addWidget(_lbl(
            "Same, but for the 10 hot buttons' own pies (set independently).",
            _C["hint"], 10))

        hot_pie_scale_row = QtWidgets.QHBoxLayout()
        hot_pie_scale_row.setSpacing(8)
        self.hot_pie_icon_scale_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.hot_pie_icon_scale_slider.setRange(50, 150)
        self.hot_pie_icon_scale_slider.setValue(
            int(round(getattr(p, "hot_pie_icon_scale", 1.0) * 100)))
        _theme.set_qss(self.hot_pie_icon_scale_slider, _SS_SLIDER)
        self.hot_pie_icon_scale_spin = self._make_value_spin(
            50, 150, self.hot_pie_icon_scale_slider.value(), "%")
        self._wire_slider_spin(self.hot_pie_icon_scale_slider, self.hot_pie_icon_scale_spin,
                                self._on_hot_pie_icon_scale_changed)
        hot_pie_scale_row.addWidget(self.hot_pie_icon_scale_slider, 1)
        hot_pie_scale_row.addWidget(self.hot_pie_icon_scale_spin)
        pie_lay.addLayout(hot_pie_scale_row)

        pie_lay.addWidget(_lbl("Hold time before the pie opens. 0 = instant.", _C["hint"], 10))

        pie_delay_row = QtWidgets.QHBoxLayout()
        pie_delay_row.setSpacing(8)
        self.pie_hold_delay_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pie_hold_delay_slider.setRange(0, 1000)
        self.pie_hold_delay_slider.setSingleStep(10)
        self.pie_hold_delay_slider.setValue(int(getattr(p, "pie_hold_delay_ms", 100)))
        _theme.set_qss(self.pie_hold_delay_slider, _SS_SLIDER)
        self.pie_hold_delay_spin = self._make_value_spin(
            0, 1000, self.pie_hold_delay_slider.value(), "ms", special_zero_text="Instant")
        self._wire_slider_spin(self.pie_hold_delay_slider, self.pie_hold_delay_spin,
                                self._on_pie_hold_delay_changed)
        pie_delay_row.addWidget(self.pie_hold_delay_slider, 1)
        pie_delay_row.addWidget(self.pie_hold_delay_spin)
        pie_lay.addLayout(pie_delay_row)

        pie_lay.addWidget(_rule())

        self.pie_dim_check = QtWidgets.QCheckBox("Dim background while a pie is open")
        self.pie_dim_check.setChecked(getattr(p, "pie_dim_enabled", True))
        _theme.set_qss(self.pie_dim_check, _SS_CHECK)
        self.pie_dim_check.setToolTip(
            "Fades everything except the pie and its origin button to make "
            "the pie items stand out more clearly."
        )
        self.pie_dim_check.toggled.connect(self._on_pie_dim_toggled)
        pie_lay.addWidget(self.pie_dim_check)

        dim_mode_row = QtWidgets.QHBoxLayout()
        dim_mode_row.setSpacing(8)
        dim_mode_lbl = _lbl("Dim scope", _C["dim"], 10)
        dim_mode_lbl.setFixedWidth(70)
        self.pie_dim_mode_combo = QtWidgets.QComboBox()
        self.pie_dim_mode_combo.addItems(["Just the panel", "Whole Maya window"])
        self.pie_dim_mode_combo.setCurrentIndex(
            1 if getattr(p, "pie_dim_mode", "panel") == "screen" else 0)
        _theme.set_qss(self.pie_dim_mode_combo, _SS_COMBO)
        self.pie_dim_mode_combo.currentIndexChanged.connect(self._on_pie_dim_mode_changed)
        dim_mode_row.addWidget(dim_mode_lbl)
        dim_mode_row.addWidget(self.pie_dim_mode_combo, 1)
        pie_lay.addLayout(dim_mode_row)

        pie_lay.addWidget(_lbl("Delay after the pie opens before dimming starts.", _C["hint"], 10))

        dim_delay_row = QtWidgets.QHBoxLayout()
        dim_delay_row.setSpacing(8)
        self.pie_dim_delay_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pie_dim_delay_slider.setRange(0, 1000)
        self.pie_dim_delay_slider.setSingleStep(10)
        self.pie_dim_delay_slider.setValue(int(getattr(p, "pie_dim_delay_ms", 150)))
        _theme.set_qss(self.pie_dim_delay_slider, _SS_SLIDER)
        self.pie_dim_delay_spin = self._make_value_spin(
            0, 1000, self.pie_dim_delay_slider.value(), "ms", special_zero_text="Instant")
        self._wire_slider_spin(self.pie_dim_delay_slider, self.pie_dim_delay_spin,
                                self._on_pie_dim_delay_changed)
        dim_delay_row.addWidget(self.pie_dim_delay_slider, 1)
        dim_delay_row.addWidget(self.pie_dim_delay_spin)
        pie_lay.addLayout(dim_delay_row)

        pie_lay.addWidget(_lbl("How fast the dim fades in once it starts (lower = faster).", _C["hint"], 10))

        dim_fade_row = QtWidgets.QHBoxLayout()
        dim_fade_row.setSpacing(8)
        self.pie_dim_fade_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pie_dim_fade_slider.setRange(0, 1000)
        self.pie_dim_fade_slider.setSingleStep(10)
        self.pie_dim_fade_slider.setValue(int(getattr(p, "pie_dim_fade_ms", 200)))
        _theme.set_qss(self.pie_dim_fade_slider, _SS_SLIDER)
        self.pie_dim_fade_spin = self._make_value_spin(
            0, 1000, self.pie_dim_fade_slider.value(), "ms", special_zero_text="Instant")
        self._wire_slider_spin(self.pie_dim_fade_slider, self.pie_dim_fade_spin,
                                self._on_pie_dim_fade_changed)
        dim_fade_row.addWidget(self.pie_dim_fade_slider, 1)
        dim_fade_row.addWidget(self.pie_dim_fade_spin)
        pie_lay.addLayout(dim_fade_row)

        pie_lay.addWidget(_lbl("How dark the dim gets.", _C["hint"], 10))

        dim_opacity_row = QtWidgets.QHBoxLayout()
        dim_opacity_row.setSpacing(8)
        self.pie_dim_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pie_dim_opacity_slider.setRange(10, 100)
        self.pie_dim_opacity_slider.setValue(int(getattr(p, "pie_dim_opacity", 55)))
        _theme.set_qss(self.pie_dim_opacity_slider, _SS_SLIDER)
        self.pie_dim_opacity_spin = self._make_value_spin(
            10, 100, self.pie_dim_opacity_slider.value(), "%")
        self._wire_slider_spin(self.pie_dim_opacity_slider, self.pie_dim_opacity_spin,
                                self._on_pie_dim_opacity_changed)
        dim_opacity_row.addWidget(self.pie_dim_opacity_slider, 1)
        dim_opacity_row.addWidget(self.pie_dim_opacity_spin)
        pie_lay.addLayout(dim_opacity_row)

        self._set_pie_dim_controls_enabled(getattr(p, "pie_dim_enabled", True))

        pie_lay.addWidget(_rule())
        pie_lay.addWidget(_lbl(
            "Rotates where the first pie item sits, and everything after it "
            "clockwise. -90\u00b0 = top (default), 0\u00b0 = right, 90\u00b0 = bottom.",
            _C["hint"], 10))

        angle_row = QtWidgets.QHBoxLayout()
        angle_row.setSpacing(8)
        self.pie_angle_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pie_angle_slider.setRange(-180, 180)
        self.pie_angle_slider.setValue(int(round(getattr(p, "pie_start_angle", -90.0))))
        _theme.set_qss(self.pie_angle_slider, _SS_SLIDER)
        self.pie_angle_spin = self._make_value_spin(
            -180, 180, self.pie_angle_slider.value(), "\u00b0")
        self._wire_slider_spin(self.pie_angle_slider, self.pie_angle_spin,
                                self._on_pie_angle_changed)
        angle_row.addWidget(self.pie_angle_slider, 1)
        angle_row.addWidget(self.pie_angle_spin)
        pie_lay.addLayout(angle_row)

        lay.addWidget(pie_card)

        # ── Input ──
        input_card, input_lay = _card()
        _section_header("INPUT", input_lay)

        self.close_on_click_check = QtWidgets.QCheckBox("Close on click")
        self.close_on_click_check.setChecked(
            getattr(p, "close_on_click", True)
        )
        _theme.set_qss(self.close_on_click_check, _SS_CHECK)
        self.close_on_click_check.setToolTip(
            "When enabled, command clicks close ModPanel: panel buttons, hot buttons, "
            "recent buttons, pie menus, ModPanel title actions, + Shelf right-click, "
            "and Settings right-click. Individual regular/hot buttons can invert this "
            "behavior in their own settings."
        )
        input_lay.addWidget(self.close_on_click_check)

        self.search_always_on_check = QtWidgets.QCheckBox(
            "Always show search bar"
        )
        self.search_always_on_check.setChecked(
            getattr(p, "search_always_on", False)
        )
        _theme.set_qss(self.search_always_on_check, _SS_CHECK)
        self.search_always_on_check.setToolTip(
            "Keep the search bar permanently visible  "
            "(default: press X to show, Escape to hide)"
        )
        input_lay.addWidget(self.search_always_on_check)

        self.recent_commands_check = QtWidgets.QCheckBox(
            "Show recent commands row"
        )
        self.recent_commands_check.setChecked(
            getattr(p, "recent_commands_enabled", True)
        )
        _theme.set_qss(self.recent_commands_check, _SS_CHECK)
        self.recent_commands_check.setToolTip(
            "Show a mini-button strip of the last 5 executed buttons "
            "above the grid"
        )
        input_lay.addWidget(self.recent_commands_check)

        self.node_detection_check = QtWidgets.QCheckBox(
            "Auto-switch to Hypershade when shader nodes are selected"
        )
        self.node_detection_check.setChecked(
            getattr(p, "node_detection_enabled", True)
        )
        _theme.set_qss(self.node_detection_check, _SS_CHECK)
        self.node_detection_check.setToolTip(
            "When the panel opens, if any selected node is a shader or "
            "material type, automatically switch to the Hypershade panel"
        )
        input_lay.addWidget(self.node_detection_check)
        lay.addWidget(input_card)

        lay.addStretch(1)
        return page
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_buttons(self):
        page, lay = self._page()
        p = self.panel

        _N = 10   # number of hot buttons

        while len(p.custom_buttons) < _N:
            p.custom_buttons.append({
                "name": "BTN{}".format(len(p.custom_buttons) + 1),
                "tooltip": "", "type": "mel", "code": "", "icon": "", "visible": False,
                "invert_close_on_click": False,
            })
        while len(p.quick_button_rc) < _N:
            p.quick_button_rc.append(
                {"name": "", "code": "", "type": "python", "icon": ""}
            )

        # Cache of icon names updated by shelf picks; read in apply_changes
        self._quick_icons = [
            (p.custom_buttons[i].get("icon", "") if i < len(p.custom_buttons) else "")
            for i in range(_N)
        ]
        self._quick_rc_icons = [
            (p.quick_button_rc[i].get("icon", "") if i < len(p.quick_button_rc) else "")
            for i in range(_N)
        ]

        # ── Visibility ── one slider controls the number of shown hot buttons.
        _section_header("VISIBILITY  —  shared across all panels", lay)
        lay.addWidget(_lbl(
            "Choose how many hot buttons are shown. The numbered buttons are visual indicators only.",
            _C["hint"], 10
        ))

        count_row = QtWidgets.QHBoxLayout()
        count_row.setSpacing(8)
        self.hot_button_count_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.hot_button_count_slider.setRange(0, _N)
        self.hot_button_count_slider.setSingleStep(1)
        self.hot_button_count_slider.setPageStep(1)
        self.hot_button_count_slider.setValue(
            max(0, min(_N, int(getattr(p, "quick_button_count", 0))))
        )
        _theme.set_qss(self.hot_button_count_slider, _SS_SLIDER)
        self.hot_button_count_spin = self._make_value_spin(
            0, _N, self.hot_button_count_slider.value(), " / {}".format(_N))
        count_row.addWidget(self.hot_button_count_slider, 1)
        count_row.addWidget(self.hot_button_count_spin)
        lay.addLayout(count_row)

        self.vis_toggle_buttons = []
        vr = QtWidgets.QHBoxLayout()
        vr.setSpacing(4)
        for i in range(_N):
            btn = QtWidgets.QPushButton("{:02d}".format(i + 1))
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setFixedWidth(30)
            btn.setFocusPolicy(QtCore.Qt.NoFocus)
            btn.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            self.vis_toggle_buttons.append(btn)
            vr.addWidget(btn)
        vr.addStretch(1)
        lay.addLayout(vr)
        self._wire_slider_spin(self.hot_button_count_slider, self.hot_button_count_spin,
                                self._on_hot_button_count_changed)
        self._refresh_vis_states()

        lay.addWidget(_rule())

        # ── Per-button editor ──
        _section_header("BUTTON EDITOR  —  shared across all panels", lay)

        self.quick_name_edits    = []
        self.quick_tooltip_edits = []
        self.quick_type_boxes    = []
        self.quick_code_edits    = []
        self.quick_close_override_checks = []
        self.quick_rc_name_edits = []
        self.quick_rc_type_boxes = []
        self.quick_rc_code_edits = []
        self._icon_preview_lbls  = []   # icon preview labels, one per hot button
        self._rc_icon_preview_lbls = []   # icon preview labels for RC actions

        btn_tabs = QtWidgets.QTabWidget()
        _theme.set_qss(btn_tabs, """
        QTabWidget::pane {{
            border:1px solid {border};
            border-radius:8px;
            background:{card};
            top: 2px;
        }}
        QTabBar::tab {{
            background:transparent; color:{hint};
            padding:5px 11px; font-size:10px;
            border-radius:6px;
            margin: 0 3px 4px 0;
        }}
        QTabBar::tab:selected {{
            background:{accent}; color:#fff; font-weight:600;
        }}
        QTabBar::tab:hover:!selected {{ background:{hover}; color:{text}; }}
        """.format(**_C))
        lay.addWidget(btn_tabs)

        for i in range(_N):
            data    = p.custom_buttons[i]
            rc_data = p.quick_button_rc[i] if i < len(p.quick_button_rc) else {}

            tp = QtWidgets.QWidget()
            _theme.set_qss(tp, "background:transparent;")
            tl = QtWidgets.QVBoxLayout(tp)
            tl.setContentsMargins(10, 10, 10, 10)
            tl.setSpacing(7)

            # meta row
            name_e = QtWidgets.QLineEdit()
            name_e.setMaxLength(6)
            name_e.setText((data.get("name", "BTN{}".format(i+1))[:6]))
            name_e.setFixedWidth(58)
            _theme.set_qss(name_e, _SS_INPUT)

            tip_e = QtWidgets.QLineEdit()
            tip_e.setText(data.get("tooltip", ""))
            tip_e.setPlaceholderText("Tooltip")
            _theme.set_qss(tip_e, _SS_INPUT)

            type_b = QtWidgets.QComboBox()
            type_b.addItems(["MEL", "Python"])
            type_b.setCurrentIndex(1 if (data.get("type","mel") or "mel").lower() == "python" else 0)
            _theme.set_qss(type_b, _SS_COMBO)

            mr = QtWidgets.QHBoxLayout()
            mr.setSpacing(6)
            def _rl(t, w=40):
                lb = _lbl(t); lb.setFixedWidth(w)
                lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                return lb
            mr.addWidget(_rl("Label",36)); mr.addWidget(name_e)
            mr.addSpacing(6)
            mr.addWidget(_rl("Tip",26)); mr.addWidget(tip_e, 1)
            mr.addSpacing(6)
            mr.addWidget(_rl("Type",30)); mr.addWidget(type_b)
            tl.addLayout(mr)

            close_override = QtWidgets.QCheckBox(
                "Opposite of global Close on click for this button")
            close_override.setChecked(
                bool(data.get("invert_close_on_click", False)))
            _theme.set_qss(close_override, _SS_CHECK)
            close_override.setToolTip(
                "This one hot button flips the global Close on click setting. "
                "It applies to left-click, right-click, and every item in this "
                "button's pie menu.")
            tl.addWidget(close_override)

            tl.addWidget(_lbl("Left-click code", _C["dim"], 10))
            code_e = QtWidgets.QTextEdit()
            code_e.setPlainText(data.get("code", ""))
            code_e.setMinimumHeight(70); code_e.setMaximumHeight(110)
            _theme.set_qss(code_e, _SS_INPUT)
            tl.addWidget(code_e)

            # Icon preview + shelf pick row
            plc_row = QtWidgets.QHBoxLayout()
            plc_row.setSpacing(6)
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setFixedSize(22, 22)
            _theme.set_qss(icon_lbl, "background:#0e1018; border:1px solid #2c3348; border-radius:3px;")
            plc_row.addWidget(icon_lbl)

            pick_lc_btn = QtWidgets.QPushButton("↓ Pick from Shelf")
            pick_lc_btn.setFixedHeight(20)
            pick_lc_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(pick_lc_btn, self._pick_btn_ss())
            # Use default-arg lambda to capture current loop values safely
            pick_lc_btn.clicked.connect(
                lambda _=False, ce=code_e, tb=type_b, il=icon_lbl, bi=i, ne=name_e, te=tip_e:
                    self._pick_from_shelf(
                        ce, tb,
                        lambda name, _il=il, _bi=bi: self._set_icon(_il, name, _bi),
                        name_widget=ne, tooltip_widget=te
                    )
            )
            plc_row.addWidget(pick_lc_btn)
            clear_lc_btn = QtWidgets.QPushButton("Clear LC Code")
            clear_lc_btn.setFixedHeight(20)
            clear_lc_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(clear_lc_btn, self._pick_btn_ss())
            clear_lc_btn.clicked.connect(lambda _=False, ce=code_e: ce.clear())
            plc_row.addWidget(clear_lc_btn)

            plc_row.addStretch(1)
            tl.addLayout(plc_row)

            tl.addWidget(_rule())

            # Pie menu — its own clearly-labeled row (not crammed among the
            # icon-pick buttons above) so it's easy to find and shows at a
            # glance how many pie items are already configured.
            pie_count = len(data.get("pie_commands", []) or [])
            pie_row = QtWidgets.QHBoxLayout()
            pie_row.setSpacing(8)
            pie_row.addWidget(_lbl("Pie Menu", _C["dim"], 10, bold=True))
            pie_count_lbl = _lbl(
                "{} item{} configured".format(pie_count, "" if pie_count == 1 else "s"),
                _C["hint"], 10)
            pie_row.addWidget(pie_count_lbl, 1)
            edit_pie_btn = QtWidgets.QPushButton("Add / Edit Pie Items")
            edit_pie_btn.setFixedHeight(22)
            edit_pie_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(edit_pie_btn, self._pick_btn_ss())
            edit_pie_btn.clicked.connect(
                lambda _=False, bi=i, lbl=pie_count_lbl: self._edit_hot_button_pie(bi, lbl))
            pie_row.addWidget(edit_pie_btn)
            tl.addLayout(pie_row)

            tl.addWidget(_rule())

            # rc header
            rc_h = QtWidgets.QHBoxLayout()
            rc_h.addWidget(_lbl("Right-click", _C["dim"], 10, bold=True))
            rc_h.addWidget(_lbl("(shared — runs whenever code below is set)", _C["hint"], 10))
            rc_h.addStretch(1)
            tl.addLayout(rc_h)

            rc_name_e = QtWidgets.QLineEdit()
            rc_name_e.setText(rc_data.get("name",""))
            rc_name_e.setPlaceholderText("Tooltip")
            _theme.set_qss(rc_name_e, _SS_INPUT)

            rc_type_b = QtWidgets.QComboBox()
            rc_type_b.addItems(["Python", "MEL"])
            rc_type_b.setCurrentIndex(0 if (rc_data.get("type","python") or "python").lower() == "python" else 1)
            _theme.set_qss(rc_type_b, _SS_COMBO)

            rcmr = QtWidgets.QHBoxLayout()
            rcmr.setSpacing(6)
            rcmr.addWidget(_rl("Tip",26)); rcmr.addWidget(rc_name_e, 1)
            rcmr.addSpacing(6)
            rcmr.addWidget(_rl("Type",30)); rcmr.addWidget(rc_type_b)
            tl.addLayout(rcmr)

            tl.addWidget(_lbl("Right-click code", _C["hint"], 10))
            rc_code_e = QtWidgets.QTextEdit()
            rc_code_e.setPlainText(rc_data.get("code",""))
            rc_code_e.setMinimumHeight(50); rc_code_e.setMaximumHeight(90)
            _theme.set_qss(rc_code_e, _SS_INPUT)
            tl.addWidget(rc_code_e)

            # Icon preview + shelf pick row (RC has its own icon, independent of LC)
            prc_row = QtWidgets.QHBoxLayout()
            prc_row.setSpacing(6)
            rc_icon_lbl = QtWidgets.QLabel()
            rc_icon_lbl.setFixedSize(22, 22)
            _theme.set_qss(rc_icon_lbl, "background:#0e1018; border:1px solid #2c3348; border-radius:3px;")
            prc_row.addWidget(rc_icon_lbl)

            pick_rc = QtWidgets.QPushButton("↓ Pick from Shelf")
            pick_rc.setFixedHeight(20)
            pick_rc.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(pick_rc, self._pick_btn_ss())
            pick_rc.clicked.connect(
                lambda _=False, ce=rc_code_e, tb=rc_type_b, te=rc_name_e,
                       il=rc_icon_lbl, bi=i:
                    self._pick_from_shelf(
                        ce, tb,
                        lambda name, _il=il, _bi=bi: self._set_rc_icon(_il, name, _bi),
                        tooltip_widget=te
                    )
            )
            prc_row.addWidget(pick_rc)
            clear_rc = QtWidgets.QPushButton("Clear RC Code")
            clear_rc.setFixedHeight(20)
            clear_rc.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(clear_rc, self._pick_btn_ss())
            clear_rc.clicked.connect(lambda _=False, ce=rc_code_e: ce.clear())
            prc_row.addWidget(clear_rc)
            prc_row.addStretch(1)
            tl.addLayout(prc_row)
            tl.addStretch(1)

            btn_tabs.addTab(tp, " {} ".format(i+1))

            self.quick_name_edits.append(name_e)
            self.quick_tooltip_edits.append(tip_e)
            self.quick_type_boxes.append(type_b)
            self.quick_code_edits.append(code_e)
            self.quick_close_override_checks.append(close_override)
            self.quick_rc_name_edits.append(rc_name_e)
            self.quick_rc_type_boxes.append(rc_type_b)
            self.quick_rc_code_edits.append(rc_code_e)
            self._icon_preview_lbls.append(icon_lbl)
            self._rc_icon_preview_lbls.append(rc_icon_lbl)

        # Load existing icon previews now that all tabs are built
        self._reload_icon_previews()

        lay.addStretch(1)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Title
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_title(self):
        page, lay = self._page()
        lay.setSpacing(12)
        p = self.panel

        # ── Panel title ──
        title_card, title_lay = _card()
        _section_header("PANEL TITLE", title_lay)
        self.panel_title_edit = QtWidgets.QLineEdit()
        self.panel_title_edit.setText(getattr(p, "panel_title", "ModPanel") or "ModPanel")
        self.panel_title_edit.setPlaceholderText("ModPanel")
        _theme.set_qss(self.panel_title_edit, _SS_INPUT)
        self.panel_title_edit.textChanged.connect(self._sync_title_to_look)
        title_lay.addWidget(self.panel_title_edit)
        lay.addWidget(title_card)

        # ── Middle-click ──
        mc_card, mc_lay = _card()
        _section_header("MIDDLE-CLICK", mc_lay)
        mc_lay.addWidget(_lbl("No default action — only runs if you set a command.", _C["hint"], 10))

        self.title_click_tooltip_edit = QtWidgets.QLineEdit()
        self.title_click_tooltip_edit.setText(getattr(p, "title_click_tooltip", "") or "")
        self.title_click_tooltip_edit.setPlaceholderText("Tooltip (shown only if a command is set below)")
        _theme.set_qss(self.title_click_tooltip_edit, _SS_INPUT)
        mc_lay.addWidget(self.title_click_tooltip_edit)

        tc_r = QtWidgets.QHBoxLayout()
        tc_r.setSpacing(6)
        self.title_click_type_box = QtWidgets.QComboBox()
        self.title_click_type_box.addItems(["Python", "MEL"])
        cur_tc = (getattr(p, "title_click_type", "python") or "python").lower()
        self.title_click_type_box.setCurrentIndex(0 if cur_tc == "python" else 1)
        _theme.set_qss(self.title_click_type_box, _SS_COMBO)
        tc_r.addWidget(_lbl("Type")); tc_r.addWidget(self.title_click_type_box); tc_r.addStretch(1)
        mc_lay.addLayout(tc_r)

        self.title_click_edit = QtWidgets.QTextEdit()
        self.title_click_edit.setPlainText(getattr(p, "title_click_code", "") or "")
        self.title_click_edit.setFixedHeight(64)
        self.title_click_edit.setPlaceholderText("Python or MEL…")
        _theme.set_qss(self.title_click_edit, _SS_INPUT)
        mc_lay.addWidget(self.title_click_edit)
        pick_mc = QtWidgets.QPushButton("↓ Pick from Shelf")
        pick_mc.setFixedHeight(20)
        pick_mc.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        _theme.set_qss(pick_mc, self._pick_btn_ss())
        pick_mc.clicked.connect(
            lambda _=False: self._pick_from_shelf(
                self.title_click_edit, self.title_click_type_box)
        )
        pm_row = QtWidgets.QHBoxLayout()
        pm_row.addWidget(pick_mc); pm_row.addStretch(1)
        mc_lay.addLayout(pm_row)
        lay.addWidget(mc_card)

        # ── Right-click ──
        rc_card, rc_lay = _card()
        _section_header("RIGHT-CLICK", rc_lay)
        rc_lay.addWidget(_lbl(
            "Default: switches panel. Set a command below to override it.",
            _C["hint"], 10))

        self.title_right_click_tooltip_edit = QtWidgets.QLineEdit()
        self.title_right_click_tooltip_edit.setText(getattr(p, "title_right_click_tooltip", "") or "")
        self.title_right_click_tooltip_edit.setPlaceholderText("Tooltip (leave blank for the default wording)")
        _theme.set_qss(self.title_right_click_tooltip_edit, _SS_INPUT)
        rc_lay.addWidget(self.title_right_click_tooltip_edit)

        tr_r = QtWidgets.QHBoxLayout()
        tr_r.setSpacing(6)
        self.title_right_click_type_box = QtWidgets.QComboBox()
        self.title_right_click_type_box.addItems(["Python", "MEL"])
        cur_tr = (getattr(p, "title_right_click_type", "python") or "python").lower()
        self.title_right_click_type_box.setCurrentIndex(0 if cur_tr == "python" else 1)
        _theme.set_qss(self.title_right_click_type_box, _SS_COMBO)
        tr_r.addWidget(_lbl("Type")); tr_r.addWidget(self.title_right_click_type_box); tr_r.addStretch(1)
        rc_lay.addLayout(tr_r)

        self.title_right_click_edit = QtWidgets.QTextEdit()
        self.title_right_click_edit.setPlainText(getattr(p, "title_right_click_code", "") or "")
        self.title_right_click_edit.setFixedHeight(64)
        self.title_right_click_edit.setPlaceholderText("Python or MEL…")
        _theme.set_qss(self.title_right_click_edit, _SS_INPUT)
        rc_lay.addWidget(self.title_right_click_edit)
        pick_tr = QtWidgets.QPushButton("↓ Pick from Shelf")
        pick_tr.setFixedHeight(20)
        pick_tr.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        _theme.set_qss(pick_tr, self._pick_btn_ss())
        pick_tr.clicked.connect(
            lambda _=False: self._pick_from_shelf(
                self.title_right_click_edit, self.title_right_click_type_box)
        )
        pt_row = QtWidgets.QHBoxLayout()
        pt_row.addWidget(pick_tr); pt_row.addStretch(1)
        rc_lay.addLayout(pt_row)
        lay.addWidget(rc_card)

        # ── Double-click ──
        dc_card, dc_lay = _card()
        _section_header("DOUBLE-CLICK", dc_lay)
        dc_lay.addWidget(_lbl(
            "Default: reloads ModPanel. Set a command below to override it.",
            _C["hint"], 10))

        self.title_double_click_tooltip_edit = QtWidgets.QLineEdit()
        self.title_double_click_tooltip_edit.setText(getattr(p, "title_double_click_tooltip", "") or "")
        self.title_double_click_tooltip_edit.setPlaceholderText("Tooltip (leave blank for the default wording)")
        _theme.set_qss(self.title_double_click_tooltip_edit, _SS_INPUT)
        dc_lay.addWidget(self.title_double_click_tooltip_edit)

        td_r = QtWidgets.QHBoxLayout()
        td_r.setSpacing(6)
        self.title_double_click_type_box = QtWidgets.QComboBox()
        self.title_double_click_type_box.addItems(["Python", "MEL"])
        cur_td = (getattr(p, "title_double_click_type", "python") or "python").lower()
        self.title_double_click_type_box.setCurrentIndex(0 if cur_td == "python" else 1)
        _theme.set_qss(self.title_double_click_type_box, _SS_COMBO)
        td_r.addWidget(_lbl("Type")); td_r.addWidget(self.title_double_click_type_box); td_r.addStretch(1)
        dc_lay.addLayout(td_r)

        self.title_double_click_edit = QtWidgets.QTextEdit()
        self.title_double_click_edit.setPlainText(getattr(p, "title_double_click_code", "") or "")
        self.title_double_click_edit.setFixedHeight(64)
        self.title_double_click_edit.setPlaceholderText("Python or MEL…")
        _theme.set_qss(self.title_double_click_edit, _SS_INPUT)
        dc_lay.addWidget(self.title_double_click_edit)
        pick_td = QtWidgets.QPushButton("↓ Pick from Shelf")
        pick_td.setFixedHeight(20)
        pick_td.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        _theme.set_qss(pick_td, self._pick_btn_ss())
        pick_td.clicked.connect(
            lambda _=False: self._pick_from_shelf(
                self.title_double_click_edit, self.title_double_click_type_box)
        )
        pd_row = QtWidgets.QHBoxLayout()
        pd_row.addWidget(pick_td); pd_row.addStretch(1)
        dc_lay.addLayout(pd_row)
        lay.addWidget(dc_card)

        lay.addStretch(1)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Workspaces
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_workspaces(self):
        page, lay = self._page()
        p = self.panel
        if self._ws_list is None:
            self._ws_list = self._load_workspaces()
        wsl = self._ws_list
        cyc = getattr(p, "workspace_cycle", ["General", "UV Editing"])

        _section_header("⚙ RIGHT-CLICK TOGGLE", lay)
        lay.addWidget(_lbl("Right-clicking the gear cycles between these two workspaces.", _C["hint"], 10))

        self.ws_a_combo = QtWidgets.QComboBox()
        self.ws_a_combo.addItems(wsl); _theme.set_qss(self.ws_a_combo, _SS_COMBO)
        ia = self.ws_a_combo.findText(cyc[0])
        if ia >= 0: self.ws_a_combo.setCurrentIndex(ia)

        self.ws_b_combo = QtWidgets.QComboBox()
        self.ws_b_combo.addItems(wsl); _theme.set_qss(self.ws_b_combo, _SS_COMBO)
        ib = self.ws_b_combo.findText(cyc[1])
        if ib >= 0: self.ws_b_combo.setCurrentIndex(ib)

        arrow = _lbl("⇄", _C["hint"], 13)
        arrow.setAlignment(QtCore.Qt.AlignCenter)
        arrow.setFixedWidth(22)

        wr = QtWidgets.QHBoxLayout()
        wr.setSpacing(6)
        la = _lbl("A"); la.setFixedWidth(16); la.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        lb = _lbl("B"); lb.setFixedWidth(16); lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        wr.addWidget(la); wr.addWidget(self.ws_a_combo, 1)
        wr.addWidget(arrow)
        wr.addWidget(lb); wr.addWidget(self.ws_b_combo, 1)
        lay.addLayout(wr)

        lay.addWidget(_rule())

        _section_header("TAB 1 AUTO-SWITCH", lay)
        lay.addWidget(_lbl("Panel switches to Tab 1 when this workspace is active.", _C["hint"], 10))

        self.uv_ws_combo = QtWidgets.QComboBox()
        self.uv_ws_combo.addItems(wsl); _theme.set_qss(self.uv_ws_combo, _SS_COMBO)
        iu = self.uv_ws_combo.findText(getattr(p, "uv_tab_workspace", "UV Editing"))
        if iu >= 0: self.uv_ws_combo.setCurrentIndex(iu)
        lay.addWidget(_field("Workspace", self.uv_ws_combo))

        lay.addStretch(1)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Look
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_look(self):
        page, lay = self._page()
        lay.setSpacing(12)
        self._look_draft = self.panel.export_look_settings()

        # The floating Apply button sits over the top-right of this tab at
        # a fixed position (see _reposition_look_apply_btn) — this spacer
        # keeps the first card clear of it even when scrolled to the top.
        lay.addSpacing(38)

        style_card, style_lay = _card()
        _section_header("UI STYLE", style_lay)
        style_lay.addWidget(_lbl(
            "Applies instantly to the panel, settings and all ModPanel windows.",
            _C["hint"], 10))
        style_row = QtWidgets.QHBoxLayout()
        style_row.setSpacing(8)
        self.ui_style_buttons = {}
        for name in _theme.STYLE_ORDER:
            b = QtWidgets.QPushButton(_theme.STYLE_LABELS[name])
            b.setCheckable(True)
            b.setFixedHeight(30)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(b, """
            QPushButton {{ background:{btn}; color:{dim}; border:1px solid {border};
                           border-radius:6px; padding:0 10px; font-size:10px; }}
            QPushButton:hover {{ background:{hover}; color:{text}; border-color:{border2}; }}
            QPushButton:checked {{ background:{sidebar_sel}; color:{accent_h};
                                   border-color:{accent}; font-weight:600; }}
            """.format(**_C))
            b.clicked.connect(lambda _=False, n=name: self._on_ui_style_clicked(n))
            self.ui_style_buttons[name] = b
            style_row.addWidget(b, 1)
        style_lay.addLayout(style_row)
        lay.addWidget(style_card)
        self._refresh_ui_style_buttons()

        identity_card, identity_lay = _card()
        _section_header("TITLE", identity_lay)
        self.look_title_edit = QtWidgets.QLineEdit()
        _theme.set_qss(self.look_title_edit, _SS_INPUT)
        self.look_title_edit.setPlaceholderText("ModPanel")
        self.look_title_edit.textChanged.connect(self._on_look_title_changed)
        identity_lay.addWidget(_field("Title Text", self.look_title_edit, 92))
        lay.addWidget(identity_card)

        colours_card, colours_lay = _card()
        _section_header("COLORS", colours_lay)
        colour_grid = QtWidgets.QGridLayout()
        colour_grid.setHorizontalSpacing(10)
        colour_grid.setVerticalSpacing(7)
        self.look_color_buttons = {}
        colour_fields = [
            ("panel_background", "Background"),
            ("panel_border", "Border"),
            ("title_bar", "Title Bar"),
            ("button", "Button"),
            ("button_hover", "Hover"),
            ("button_pressed", "Pressed"),
            ("button_selected", "Selected"),
            ("text", "Text"),
            ("icon", "UI Icon"),
            ("accent", "Accent"),
        ]
        for i, (key, label) in enumerate(colour_fields):
            r, c = divmod(i, 2)
            holder = QtWidgets.QWidget()
            _theme.set_qss(holder, "background:transparent;")
            hl = QtWidgets.QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(6)
            lab = _lbl(label, _C["dim"], 10)
            lab.setFixedWidth(68)
            btn = _ColorButton(self._look_draft.get(key, "#ffffff"))
            btn.colorChanged.connect(
                lambda value, k=key: self._set_look_value(k, value))
            self.look_color_buttons[key] = btn
            hl.addWidget(lab)
            hl.addWidget(btn, 1)
            colour_grid.addWidget(holder, r, c)
        colours_lay.addLayout(colour_grid)
        lay.addWidget(colours_card)

        geometry_card, geometry_lay = _card()
        _section_header("SHAPE & SPACING", geometry_lay)
        self.look_value_controls = {}

        def _spin(key, label, low, high, suffix=" px"):
            w = QtWidgets.QSpinBox()
            w.setRange(low, high)
            w.setSuffix(suffix)
            _theme.set_qss(w, _SS_SPIN)
            w.valueChanged.connect(lambda value, k=key: self._set_look_value(k, value))
            self.look_value_controls[key] = w
            geometry_lay.addWidget(_field(label, w, 116))

        _spin("opacity", "Opacity", 20, 100, "%")
        _spin("border_thickness", "Border Thickness", 0, 8)
        _spin("corner_radius", "Corner Radius", 0, 32)
        _spin("button_padding", "Button Padding", 0, 18)
        _spin("button_spacing", "Button Spacing", 0, 50)

        scale = QtWidgets.QDoubleSpinBox()
        scale.setRange(0.5, 10.0)
        scale.setDecimals(2)
        scale.setSingleStep(0.1)
        scale.setSuffix("x")
        _theme.set_qss(scale, _SS_SPIN)
        scale.valueChanged.connect(
            lambda value: self._set_look_value("visual_scale", value))
        self.look_value_controls["visual_scale"] = scale
        geometry_lay.addWidget(_field("Visual Scale", scale, 116))
        lay.addWidget(geometry_card)

        actions_card, actions_lay = _card()
        _section_header("LOOK PRESETS", actions_lay)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.look_reset_btn = QtWidgets.QPushButton("Reset to Default")
        self.look_import_btn = QtWidgets.QPushButton("Import Look")
        self.look_export_btn = QtWidgets.QPushButton("Export Look")
        for b in (self.look_reset_btn, self.look_import_btn, self.look_export_btn):
            b.setFixedHeight(30)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(b, """
            QPushButton {{ background:{btn}; color:{text}; border:1px solid {border};
                           border-radius:6px; padding:0 10px; font-size:10px; }}
            QPushButton:hover {{ background:{hover}; border-color:{accent}; }}
            """.format(**_C))
            row.addWidget(b, 1)
        actions_lay.addLayout(row)
        self.look_reset_btn.clicked.connect(self._reset_look_draft)
        self.look_import_btn.clicked.connect(self._import_look)
        self.look_export_btn.clicked.connect(self._export_look)
        lay.addWidget(actions_card)

        lay.addStretch(1)
        self._sync_look_controls()
        return page

    def _set_look_value(self, key, value):
        if not isinstance(getattr(self, "_look_draft", None), dict):
            self._look_draft = self.panel.export_look_settings()
        self._look_draft[key] = value
        self._look_draft = self.panel.normalize_look_settings(self._look_draft)

        # The Look tab exposes the same canonical title/scale/spacing values
        # as their older tabs. Keep both editors synchronized without touching
        # the real panel.
        if key == "title_text" and 2 in self._loaded_tabs:
            self.panel_title_edit.blockSignals(True)
            self.panel_title_edit.setText(self._look_draft["title_text"])
            self.panel_title_edit.blockSignals(False)
        elif key == "visual_scale" and 0 in self._loaded_tabs:
            self.panel_scale_spin.blockSignals(True)
            self.panel_scale_slider.blockSignals(True)
            self.panel_scale_spin.setValue(self._look_draft["visual_scale"])
            self.panel_scale_slider.setValue(
                int(round(self._look_draft["visual_scale"] * 10)))
            self.panel_scale_spin.blockSignals(False)
            self.panel_scale_slider.blockSignals(False)
        elif key == "button_spacing" and 0 in self._loaded_tabs:
            self.pad_spin.blockSignals(True)
            self.pad_spin.setValue(self._look_draft["button_spacing"])
            self.pad_spin.blockSignals(False)

    def _on_look_title_changed(self, text):
        self._set_look_value("title_text", text.strip() or "ModPanel")

    def _sync_title_to_look(self, text):
        if 4 not in self._loaded_tabs:
            return
        value = text.strip() or "ModPanel"
        self._look_draft["title_text"] = value
        if hasattr(self, "look_title_edit") and self.look_title_edit.text() != value:
            self.look_title_edit.blockSignals(True)
            self.look_title_edit.setText(value)
            self.look_title_edit.blockSignals(False)
    def _sync_look_controls(self):
        if not hasattr(self, "look_title_edit"):
            return
        self._look_draft = self.panel.normalize_look_settings(self._look_draft)
        self.look_title_edit.blockSignals(True)
        self.look_title_edit.setText(self._look_draft["title_text"])
        self.look_title_edit.blockSignals(False)
        for key, btn in self.look_color_buttons.items():
            btn.set_colour(self._look_draft[key], emit=False)
        for key, control in self.look_value_controls.items():
            control.blockSignals(True)
            control.setValue(self._look_draft[key])
            control.blockSignals(False)
    def _refresh_ui_style_buttons(self):
        current = _theme.current_style()
        for name, b in getattr(self, "ui_style_buttons", {}).items():
            b.blockSignals(True)
            b.setChecked(name == current)
            b.blockSignals(False)

    def _on_ui_style_clicked(self, name):
        """Switch UI style presets live — no Apply/Save needed."""
        try:
            self.panel.apply_ui_style(name, base_look=self._look_draft, save=True)
        except Exception as e:
            try:
                import maya.cmds as cmds
                cmds.warning("ModPanel: could not apply UI style: {}".format(e))
            except Exception:
                pass
        self._look_draft = self.panel.export_look_settings()
        self._sync_look_controls()
        self._refresh_ui_style_buttons()

    def _reset_look_draft(self):
        # "Default" means the active UI style's preset Look.
        preset = dict(self.panel.normalize_look_settings({}))
        preset.update(_theme.look_preset(_theme.current_style()))
        self._look_draft = self.panel.normalize_look_settings(preset)
        self._sync_look_controls()
        self._set_look_value("title_text", self._look_draft["title_text"])
        self._set_look_value("visual_scale", self._look_draft["visual_scale"])
        self._set_look_value("button_spacing", self._look_draft["button_spacing"])

    def _import_look(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import ModPanel Look", "",
            "ModPanel Look (*.json);;JSON Files (*.json)")
        if not path:
            return
        try:
            import json
            with open(path, "r") as f:
                raw = json.load(f)
            payload = raw.get("look", raw) if isinstance(raw, dict) else {}
            if not isinstance(payload, dict):
                raise ValueError("The selected file does not contain Look settings.")
            self._look_draft = self.panel.normalize_look_settings(payload)
            self._sync_look_controls()
            self._set_look_value("title_text", self._look_draft["title_text"])
            self._set_look_value("visual_scale", self._look_draft["visual_scale"])
            self._set_look_value("button_spacing", self._look_draft["button_spacing"])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Import Look",
                                          "Could not import this Look file:\n{}".format(e))

    def _export_look(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export ModPanel Look", "phoenix_panel_look.json",
            "ModPanel Look (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            import json
            with open(path, "w") as f:
                json.dump({"version": 1, "look": self._look_draft}, f, indent=2)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export Look",
                                          "Could not export the Look file:\n{}".format(e))

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Data
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_data(self):
        page, lay = self._page()

        _section_header("PRESETS  —  panels + hot buttons + look", lay)
        lay.addWidget(_lbl("Exports every panel, shared hot buttons, title actions, and appearance.", _C["hint"], 10))

        self.import_btn = QtWidgets.QPushButton("Import")
        self.export_btn = QtWidgets.QPushButton("Export")
        for b in (self.import_btn, self.export_btn):
            b.setFixedHeight(30)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(b, """
            QPushButton {{
                background:{btn}; color:{text};
                border:1px solid {border}; border-radius:6px; font-size:11px;
            }}
            QPushButton:hover {{ background:{hover}; border-color:{border2}; }}
            """.format(**_C))
        ie = QtWidgets.QHBoxLayout()
        ie.setSpacing(8)
        ie.addWidget(self.import_btn, 1); ie.addWidget(self.export_btn, 1)
        lay.addLayout(ie)

        lay.addWidget(_rule())

        _section_header("DANGER ZONE", lay)
        self.delete_all_btn = QtWidgets.QPushButton("Delete All Buttons  (current panel only)")
        self.delete_all_btn.setFixedHeight(30)
        self.delete_all_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        _theme.set_qss(self.delete_all_btn, """
        QPushButton {{
            background:transparent; color:{red_dim};
            border:1px solid {red}; border-radius:6px; font-size:11px;
        }}
        QPushButton:hover {{ background:{red}; color:#fff; }}
        """.format(**_C))
        lay.addWidget(self.delete_all_btn)

        self.reset_all_btn = QtWidgets.QPushButton(
            "Reset Everything  —  panels · hot buttons · title codes · look"
        )
        self.reset_all_btn.setFixedHeight(30)
        self.reset_all_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        _theme.set_qss(self.reset_all_btn, """
        QPushButton {{
            background:transparent; color:{red_dim};
            border:1px solid {red}; border-radius:6px;
            font-size:11px; font-weight:600;
        }}
        QPushButton:hover {{ background:{red}; color:#fff; }}
        """.format(**_C))
        lay.addWidget(self.reset_all_btn)

        self.import_btn.clicked.connect(self._import_config)
        self.export_btn.clicked.connect(self._export_config)
        self.delete_all_btn.clicked.connect(self._delete_all_confirm)
        self.reset_all_btn.clicked.connect(self._reset_all_confirm)

        lay.addStretch(1)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Free Stuff
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_free_stuff(self):
        page, lay = self._page()
        lay.setSpacing(10)

        _section_header("FREE STUFF", lay)

        from . import free_stuff as _fs
        self._free_stuff_panel = _fs.FreeStuffPanel(self.panel, parent=page)
        lay.addWidget(self._free_stuff_panel, 1)

        return page

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Credits
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_credits(self):
        page, lay = self._page()
        lay.setSpacing(10)

        # ── Blue palette — brightened for readability; kept the blue identity
        # but several tones here were previously too close to the background
        # to read comfortably (label/dim/feat_d especially).
        CR = {
            "bg":       "#070c18",
            "hdr":      "#0d1a30",
            "border":   "#1e4a86",
            "title":    "#8cccff",
            "symbol":   "#4a8de8",
            "author":   "#7cbaff",
            "body":     "#c2ddf5",
            "dim":      "#6f9ac8",
            "label":    "#7ea4d0",
            "value":    "#b8dafa",
            "feat_t":   "#a8d0f5",
            "feat_d":   "#82a8d2",
            "bullet":   "#5a9af0",
            "sep":      "#1c4278",
            "badge_bg": "#0f2440",
            "badge_b":  "#2f649c",
            "badge_t":  "#8cc4f5",
        }

        def _t(text, color, size, bold=False, wrap=False, align=None):
            lbl = QtWidgets.QLabel(text)
            if align is not None:
                lbl.setAlignment(align)
            if wrap:
                lbl.setWordWrap(True)
            b = "font-weight:bold;" if bold else ""
            _theme.set_qss(lbl, "background:transparent;color:{};font-size:{}px;{}".format(color, size, b))
            return lbl

        def _sep():
            f = QtWidgets.QFrame()
            f.setFrameShape(QtWidgets.QFrame.HLine)
            _theme.set_qss(f, "color:{};".format(CR["sep"]))
            return f

        def _badge(text):
            lbl = QtWidgets.QLabel("  {}  ".format(text))
            _theme.set_qss(lbl, """
                background:{bg};color:{t};
                border:1px solid {b};border-radius:3px;
                font-size:9px;padding:1px 0;
            """.format(bg=CR["badge_bg"], t=CR["badge_t"], b=CR["badge_b"]))
            return lbl

        def _kv_row(key, value):
            w = QtWidgets.QWidget()
            _theme.set_qss(w, "background:transparent;")
            h = QtWidgets.QHBoxLayout(w)
            h.setContentsMargins(0, 2, 0, 2)
            h.setSpacing(0)
            kl = _t(key, CR["label"], 10)
            kl.setFixedWidth(130)
            h.addWidget(kl)
            h.addWidget(_t(value, CR["value"], 11))
            h.addStretch(1)
            return w

        def _feature_row(title, detail):
            w = QtWidgets.QWidget()
            _theme.set_qss(w, "background:transparent;")
            h = QtWidgets.QHBoxLayout(w)
            h.setContentsMargins(0, 2, 0, 2)
            h.setSpacing(10)
            dot = _t("◆", CR["bullet"], 8)
            dot.setFixedWidth(10)
            dot.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
            h.addWidget(dot)
            col = QtWidgets.QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(_t(title, CR["feat_t"], 11, bold=True))
            col.addWidget(_t(detail, CR["feat_d"], 10))
            h.addLayout(col, 1)
            return w

        # ── OUTER CARD ────────────────────────────────────────────────────────
        outer = QtWidgets.QFrame()
        outer.setObjectName("CredOuter")
        _theme.set_qss(outer, """
        QFrame#CredOuter {{
            background:{bg};
            border:1px solid {border};
            border-radius:10px;
        }}
        """.format(**CR))
        ol = QtWidgets.QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)

        # ── HEADER BLOCK ──────────────────────────────────────────────────────
        hdr_w = QtWidgets.QWidget()
        hdr_w.setObjectName("CredHdr")
        _theme.set_qss(hdr_w, "QWidget#CredHdr{{background:{hdr};border-radius:10px 10px 0 0;}}".format(**CR))
        hl = QtWidgets.QVBoxLayout(hdr_w)
        hl.setContentsMargins(22, 22, 22, 18)
        hl.setSpacing(8)

        # Name row + badges
        name_row = QtWidgets.QHBoxLayout()
        name_row.setSpacing(8)
        name_lbl = _t("◈   ModPanel", CR["title"], 20, bold=True)
        name_row.addWidget(name_lbl)
        name_row.addStretch(1)
        name_row.addWidget(_badge("v 1.0"))
        name_row.addWidget(_badge("Maya 2027+"))
        hl.addLayout(name_row)

        # Tagline
        hl.addWidget(_t(
            "A modular floating shelf grid for Autodesk Maya —\n"
            "built for speed, clarity, and a frictionless workflow.",
            CR["body"], 11, wrap=True
        ))

        # Tech stack badges
        badge_row = QtWidgets.QHBoxLayout()
        badge_row.setSpacing(5)
        for tag in ["Python 3", "PySide6 / PySide2", "Qt5 / Qt6", "Maya API"]:
            badge_row.addWidget(_badge(tag))
        badge_row.addStretch(1)
        hl.addLayout(badge_row)
        ol.addWidget(hdr_w)

        # ── BODY ──────────────────────────────────────────────────────────────
        body_w = QtWidgets.QWidget()
        _theme.set_qss(body_w, "background:transparent;")
        bl = QtWidgets.QVBoxLayout(body_w)
        bl.setContentsMargins(22, 16, 22, 20)
        bl.setSpacing(8)

        # ── Author ──
        bl.addWidget(_sep())
        bl.addWidget(_t("CREATED BY", CR["dim"], 9, bold=True))
        author_row = QtWidgets.QHBoxLayout()
        author_row.setSpacing(8)
        author_row.addWidget(_t("Vibe Phoenix", CR["author"], 15, bold=True))
        author_row.addStretch(1)
        bl.addLayout(author_row)

        links_row = QtWidgets.QHBoxLayout()
        links_row.setSpacing(12)

        def _social_link(text, url, glow_color):
            btn = QtWidgets.QPushButton(text)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            btn.setFixedHeight(34)
            _theme.set_qss(btn, """
            QPushButton {{
                background: {bg};
                color: {fg};
                border: 1.5px solid {border};
                border-radius: 17px;
                padding: 0 18px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {hover_bg};
                border: 1.5px solid {glow};
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {pressed_bg};
                border: 1.5px solid {glow};
            }}
            """.format(
                bg=CR["badge_bg"], fg=CR["value"], border=CR["border"],
                hover_bg="#232838", pressed_bg=CR["hdr"],
                glow=glow_color,
            ))
            btn.clicked.connect(lambda _=False, u=url: QtGui.QDesktopServices.openUrl(QtCore.QUrl(u)))
            # A soft glow behind the pill via a drop-shadow effect — this is
            # a real widget button now (not a plain text link), so genuine
            # hover/pressed states and an actual glow are both possible.
            glow_fx = QtWidgets.QGraphicsDropShadowEffect(btn)
            glow_fx.setColor(QtGui.QColor(glow_color))
            glow_fx.setBlurRadius(18)
            glow_fx.setOffset(0, 0)
            btn.setGraphicsEffect(glow_fx)
            return btn

        links_row.addWidget(_social_link("▶  YouTube", "https://www.youtube.com/@VibePhoenix.", "#ff4d4d"))
        links_row.addWidget(_social_link("◉  Instagram", "https://www.instagram.com/vibephoenix/", "#e05fc4"))
        links_row.addStretch(1)
        bl.addLayout(links_row)

        # ── Build info ──
        bl.addWidget(_sep())
        bl.addWidget(_t("BUILD INFO", CR["dim"], 9, bold=True))
        for k, v in [
            ("VERSION",       "1.0"),
            ("COMPATIBILITY", "Maya 2027 +"),
            ("FRAMEWORK",     "PySide6  /  PySide2  (Qt 5 & 6)"),
            ("LANGUAGE",      "Python 3"),
            ("ARCHITECTURE",  "Multi-file package  —  lazy-loaded"),
        ]:
            bl.addWidget(_kv_row(k, v))

        # ── Features ──
        bl.addWidget(_sep())
        bl.addWidget(_t("FEATURES", CR["dim"], 9, bold=True))
        for title, detail in [
            ("3 Main Panels",
             "General · UV Editing · Hypershade — workspace auto-detected on open"),
            ("4 Hidden Panels",
             "Q, W, E, R keyboard shortcuts — same grid system, never shown in tab bar"),
            ("Shared Hot Buttons",
             "10 quick-launch buttons pinned to every panel — one config, all panels"),
            ("Shelf Picker",
             "Adds any Maya shelf button with icon, label, and tooltip intact"),
            ("Drag & Drop Reposition",
             "Right-click any button → Reposition — ghost preview follows the cursor"),
            ("Keyboard Navigation",
             "1/2/3 switches main panels · Q/W/E/R opens hidden ones · panel auto-resizes"),
            ("Workspace Toggle",
             "Right-click ⚙ to cycle between two configured Maya workspace layouts"),
            ("Import  /  Export",
             "One JSON file carries all 7 panels' buttons plus hot button config"),
        ]:
            bl.addWidget(_feature_row(title, detail))

        ol.addWidget(body_w)
        lay.addWidget(outer)
        return page


    # ── Workspace loader ──────────────────────────────────────────────────────

    # ── Slider/spinbox sync ───────────────────────────────────────────────────
    def _wire_slider_spin(self, slider, spin, on_change):
        """Keep `slider` and `spin` mutually in sync, and call `on_change(value)`
        whichever one the user actually moved. Qt's setValue() only emits
        valueChanged when the value genuinely differs, so this can't loop."""
        def _from_slider(v):
            spin.blockSignals(True)
            spin.setValue(v)
            spin.blockSignals(False)
            on_change(v)

        def _from_spin(v):
            slider.blockSignals(True)
            slider.setValue(int(round(v)))
            slider.blockSignals(False)
            on_change(int(round(v)))

        slider.valueChanged.connect(_from_slider)
        spin.valueChanged.connect(_from_spin)

    @staticmethod
    def _make_value_spin(lo, hi, value, suffix="", special_zero_text=None):
        """A small QSpinBox meant to sit next to a slider, showing/accepting
        the exact same value (with an optional suffix, and optional special
        text at the minimum — e.g. "Instant" instead of "0ms")."""
        spin = QtWidgets.QSpinBox()
        spin.setRange(lo, hi)
        if suffix:
            spin.setSuffix(suffix)
        if special_zero_text:
            spin.setSpecialValueText(special_zero_text)
        spin.setValue(value)
        _theme.set_qss(spin, _SS_SPIN)
        spin.setFixedWidth(68)
        spin.setAlignment(QtCore.Qt.AlignRight)
        return spin

    # ── Shelf-picker helper ───────────────────────────────────────────────────
    @staticmethod
    def _pick_btn_ss():
        return """QPushButton {{
            background:{btn}; color:{dim}; border:1px solid {border};
            border-radius:6px; font-size:10px; padding:3px 10px;
        }}
        QPushButton:hover {{ background:{hover}; color:{text}; border-color:{border2}; }}
        QPushButton:pressed {{ background:{bg}; }}
        """.format(**_C)

    def _pick_from_shelf(self, code_widget, type_combo, icon_callback=None,
                          name_widget=None, tooltip_widget=None):
        """Open the shelf picker; fill code_widget and type_combo.
        If icon_callback is provided it is called with the icon name (str).
        If name_widget/tooltip_widget are provided, they're auto-filled from
        the picked shelf button's overlay label / annotation so adding a
        tool button from the shelf sets everything in one go."""
        try:
            from .shelf_picker import ShelfPickerDialog as _SPD
        except ImportError:
            try:
                from phoenix_panel.shelf_picker import ShelfPickerDialog as _SPD
            except ImportError:
                return
        dlg = _SPD(parent=self)
        accepted = dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        if accepted != QtWidgets.QDialog.Accepted:
            return
        selected = dlg.selected_buttons()
        if not selected:
            return
        btn  = selected[0]
        cmd  = btn.get("command", "")
        src  = (btn.get("sourceType", "mel") or "mel").lower()
        icon = btn.get("icon", "")
        code_widget.setPlainText(cmd)

        # Auto-detect MEL vs Python from the shelf button and switch the type
        # combo to match. Match by item TEXT, not a hardcoded index — the LC
        # combo is ordered ["MEL","Python"] while the RC combo is ordered
        # ["Python","MEL"], so a fixed index silently picked the wrong
        # language depending on which combo this was called on.
        target = "MEL" if src == "mel" else "Python"
        idx = type_combo.findText(target, QtCore.Qt.MatchFixedString)
        if idx >= 0:
            type_combo.setCurrentIndex(idx)

        if icon_callback:
            icon_callback(icon)
        if name_widget is not None:
            label = (btn.get("label", "") or "").strip() or (btn.get("name", "") or "").strip()
            max_len = name_widget.maxLength()
            if max_len and max_len > 0:
                label = label[:max_len]
            name_widget.setText(label)
        if tooltip_widget is not None:
            tooltip_widget.setText((btn.get("annotation", "") or "").strip())

    def _set_icon(self, label_widget, icon_name, btn_index):
        """Store icon name in _quick_icons and update the preview label."""
        if btn_index < len(self._quick_icons):
            self._quick_icons[btn_index] = icon_name
        if icon_name:
            try:
                from .utils import resolve_maya_icon as _rmi
                label_widget.setPixmap(_rmi(icon_name).pixmap(18, 18))
                return
            except Exception:
                pass
        label_widget.setPixmap(QtGui.QPixmap())

    def _edit_hot_button_pie(self, btn_index, count_label=None):
        """Open the compact pie-command editor for hot button `btn_index`.
        Hot buttons have no context menu (right-click already runs the RC
        action directly), so this is their only editing entry point."""
        p = self.panel
        while len(p.custom_buttons) <= btn_index:
            p.custom_buttons.append({
                "name": "BTN{}".format(len(p.custom_buttons) + 1),
                "tooltip": "", "type": "mel", "code": "", "icon": "",
                "visible": False, "pie_commands": [],
            })
        data = p.custom_buttons[btn_index]
        title = "Edit Pie Commands — {}".format(
            (data.get("name") or "Hot Button {}".format(btn_index + 1)).strip())

        def _get():
            return data.get("pie_commands", [])

        def _set(new_list):
            data["pie_commands"] = new_list
            p.save_global_state()
            if getattr(p, "_ui_built", False):
                p.update_quick_buttons()
            if count_label is not None:
                n = len(new_list)
                count_label.setText("{} item{} configured".format(n, "" if n == 1 else "s"))

        def _get_angle():
            return data.get("pie_start_angle")

        def _set_angle(value):
            data["pie_start_angle"] = value
            p.save_global_state()

        p._ignore_close = True
        try:
            from .pie_editor import PieCommandEditorDialog
            from .utils import resolve_maya_icon as _rmi
            dlg = PieCommandEditorDialog(self, title, _get, _set, icon_resolver=_rmi,
                                          get_angle=_get_angle, set_angle=_set_angle)
            dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        except Exception as e:
            try:
                import maya.cmds as cmds
                cmds.warning("ModPanel: could not open pie editor: {}".format(e))
            except Exception:
                pass
        finally:
            p._ignore_close = False

    def _open_hot_button_reorder(self):
        """Drag-to-reorder dialog for the 10 hot buttons. Uses Qt's own
        internal-move list drag-and-drop (well-tested, no custom event
        filters needed) rather than a live drag directly in the title bar.
        Reordering moves each hot button's ENTIRE record together — name,
        tooltip, code type, code, icon, pie commands — plus its paired
        right-click action, since both are parallel arrays indexed by slot."""
        p = self.panel
        while len(p.custom_buttons) < 10:
            p.custom_buttons.append({
                "name": "BTN{}".format(len(p.custom_buttons) + 1),
                "tooltip": "", "type": "mel", "code": "", "icon": "",
                "visible": False, "pie_commands": [],
            })
        while len(p.quick_button_rc) < 10:
            p.quick_button_rc.append(
                {"name": "", "code": "", "type": "python", "icon": ""})

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Reorder Hot Buttons")
        dlg.resize(320, 440)
        _theme.set_qss(dlg, "background:#1b1e29; color:#dfe3ff;")
        lay = QtWidgets.QVBoxLayout(dlg)

        hint = QtWidgets.QLabel(
            "Drag to reorder. Everything about a hot button — code, icon, "
            "tooltip, pie items, and its right-click action — moves with it.")
        hint.setWordWrap(True)
        _theme.set_qss(hint, "color:#8894c0; font-size:10px;")
        lay.addWidget(hint)

        list_w = QtWidgets.QListWidget()
        list_w.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        list_w.setDefaultDropAction(QtCore.Qt.MoveAction)
        list_w.setIconSize(QtCore.QSize(22, 22))
        _theme.set_qss(list_w, """
        QListWidget {
            background:#14161f; color:#dfe3ff; border:1px solid #2c3348;
            border-radius:4px; font-size:11px;
        }
        QListWidget::item { padding:6px; border-radius:3px; }
        QListWidget::item:selected { background:#2a3050; }
        """)
        try:
            from .utils import resolve_maya_icon as _rmi
        except Exception:
            _rmi = None
        for i in range(10):
            data = p.custom_buttons[i]
            name = (data.get("name") or "").strip() or "BTN{}".format(i + 1)
            item = QtWidgets.QListWidgetItem("{}. {}".format(i + 1, name))
            icon_name = data.get("icon", "")
            if icon_name and _rmi is not None:
                try:
                    item.setIcon(_rmi(icon_name))
                except Exception:
                    pass
            item.setData(QtCore.Qt.UserRole, i)
            list_w.addItem(item)
        lay.addWidget(list_w, 1)

        btn_row = QtWidgets.QHBoxLayout()
        save_btn   = QtWidgets.QPushButton("Save Order")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        _theme.set_qss(cancel_btn, self._pick_btn_ss())
        _theme.set_qss(save_btn, self._pick_btn_ss())
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

        def _save():
            order = [list_w.item(i).data(QtCore.Qt.UserRole)
                     for i in range(list_w.count())]
            if len(order) != 10 or sorted(order) != list(range(10)):
                dlg.reject()
                return
            p.custom_buttons  = [p.custom_buttons[i]  for i in order]
            p.quick_button_rc = [p.quick_button_rc[i] for i in order]
            p.save_global_state()
            if getattr(p, "_ui_built", False):
                p.update_quick_buttons()
            # This Settings window's own per-button editor tab (if already
            # visited this session) has widgets bound to slot index, holding
            # whatever was in that slot BEFORE the reorder. Without this,
            # clicking the main Settings Save afterward would silently
            # overwrite the new order with that stale data. refresh_from_panel
            # re-populates every currently-loaded tab straight from the panel,
            # which we just updated above.
            self.refresh_from_panel()
            dlg.accept()

        save_btn.clicked.connect(_save)
        cancel_btn.clicked.connect(dlg.reject)

        p._ignore_close = True
        try:
            dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        finally:
            p._ignore_close = False

    def _set_rc_icon(self, label_widget, icon_name, btn_index):
        """Store icon name in _quick_rc_icons and update the RC preview label.
        Independent of _set_icon so the right-click action can carry its own
        icon rather than inheriting whatever the left-click icon is."""
        if btn_index < len(self._quick_rc_icons):
            self._quick_rc_icons[btn_index] = icon_name
        if icon_name:
            try:
                from .utils import resolve_maya_icon as _rmi
                label_widget.setPixmap(_rmi(icon_name).pixmap(18, 18))
                return
            except Exception:
                pass
        label_widget.setPixmap(QtGui.QPixmap())

    def _reload_icon_previews(self):
        """Load existing icons into preview labels — called after all tabs are built."""
        for i, lbl in enumerate(getattr(self, "_icon_preview_lbls", [])):
            icon_name = self._quick_icons[i] if i < len(self._quick_icons) else ""
            if icon_name:
                try:
                    from .utils import resolve_maya_icon as _rmi
                    lbl.setPixmap(_rmi(icon_name).pixmap(18, 18))
                except Exception:
                    pass
        for i, lbl in enumerate(getattr(self, "_rc_icon_preview_lbls", [])):
            icon_name = self._quick_rc_icons[i] if i < len(self._quick_rc_icons) else ""
            if icon_name:
                try:
                    from .utils import resolve_maya_icon as _rmi
                    lbl.setPixmap(_rmi(icon_name).pixmap(18, 18))
                except Exception:
                    pass

    # ── Import choices dialog ─────────────────────────────────────────────────
    def _show_import_choices(self, cfg):
        """Show a dialog for the user to pick which parts of the preset to import.
        Returns a choices dict, or None if cancelled.
        """
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Import Options")
        dlg.setWindowFlags(
            QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint
        )
        dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        outer = QtWidgets.QVBoxLayout(dlg)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = QtWidgets.QWidget()
        shell.setObjectName("ImpShell")
        _theme.set_qss(shell, """
        QWidget#ImpShell {{
            background:{bg}; border-radius:8px; border:1px solid {border};
        }}
        """.format(**_C))
        outer.addWidget(shell)

        sl = QtWidgets.QVBoxLayout(shell)
        sl.setContentsMargins(20, 16, 20, 16)
        sl.setSpacing(10)

        # Header
        hdr = QtWidgets.QLabel("Import Preset Options")
        _theme.set_qss(hdr, "color:{text}; font-size:13px; font-weight:bold; background:transparent;".format(**_C))
        sl.addWidget(hdr)

        hint = QtWidgets.QLabel("Choose which sections to import:")
        _theme.set_qss(hint, "color:{dim}; font-size:10px; background:transparent;".format(**_C))
        sl.addWidget(hint)

        # Determine what the preset contains
        has_panels  = bool(cfg.get("tabs"))
        has_hotbtns = bool(cfg.get("quick_buttons"))
        has_title   = any(
            t.get("title_click_code") or t.get("title_right_click_code")
            for t in cfg.get("tabs", {}).values()
            if isinstance(t, dict)
        )
        has_look    = isinstance(cfg.get("look"), dict)

        def _ck(label, checked, enabled=True):
            cb = QtWidgets.QCheckBox(label)
            cb.setChecked(checked and enabled)
            cb.setEnabled(enabled)
            _theme.set_qss(cb, _SS_CHECK)
            return cb

        ck_panels  = _ck("Panel Buttons  (all 7 panels)",       True, has_panels)
        ck_hotbtns = _ck("Hot Button Config  (10 quick buttons)", True, has_hotbtns)
        ck_title   = _ck("Title Click Actions  (per panel)",     True, has_title)
        ck_look    = _ck("Look / Appearance",                    True, has_look)

        for cb in (ck_panels, ck_hotbtns, ck_title, ck_look):
            sl.addWidget(cb)

        # Buttons
        br = QtWidgets.QHBoxLayout()
        br.setSpacing(8)
        br.addStretch(1)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setFixedHeight(28)
        _theme.set_qss(cancel_btn, """
        QPushButton {{ background:{btn}; color:{text}; border:1px solid {border};
                       border-radius:4px; font-size:11px; padding:0 16px; }}
        QPushButton:hover {{ background:{hover}; }}
        """.format(**_C))
        cancel_btn.clicked.connect(dlg.reject)
        br.addWidget(cancel_btn)

        ok_btn = QtWidgets.QPushButton("Import")
        ok_btn.setFixedHeight(28)
        _theme.set_qss(ok_btn, """
        QPushButton {{ background:{accent}; color:#fff;
                       border-radius:4px; font-size:11px; font-weight:bold; padding:0 16px; }}
        QPushButton:hover {{ background:#5a8fd8; }}
        """.format(**_C))
        ok_btn.clicked.connect(dlg.accept)
        br.addWidget(ok_btn)
        sl.addLayout(br)

        dlg.setMinimumWidth(340)
        accepted = dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        if accepted != QtWidgets.QDialog.Accepted:
            return None
        return {
            "panels":        ck_panels.isChecked(),
            "quick_buttons": ck_hotbtns.isChecked(),
            "title_actions": ck_title.isChecked(),
            "look":          ck_look.isChecked(),
        }

    # ── Workspace loader (original, kept) ────────────────────────────────────
    def _load_workspaces(self):
        try:
            import os as _os, maya.cmds as _mc
            _B = ["General", "UV Editing", "Rigging", "Sculpting",
                  "Rendering", "XGen", "Motion Graphics"]
            _k = {w.replace(" ","").lower(): w for w in _B}
            _d = _os.path.join((_mc.internalVar(userPrefDir=True) or "").rstrip("/\\"), "workspaces")
            _f = set()
            if _os.path.isdir(_d):
                for fn in _os.listdir(_d):
                    if fn.endswith(".json"):
                        n = fn[:-5].replace("_"," ")
                        _f.add(_k.get(n.replace(" ","").lower(), n))
            return sorted(set(_B) | _f)
        except Exception:
            return ["General","UV Editing","Rigging","Sculpting",
                    "Rendering","XGen","Motion Graphics"]

    # ── Hot-button count / visual indicators ──────────────────────────────────
    def _style_vis(self, btn, state, locked=False):
        if state:
            _theme.set_qss(btn, """
            QPushButton {{
                background:{green}; color:#fff;
                border-radius:3px; font-size:10px; font-weight:bold;
            }}
            """.format(**_C))
        else:
            _theme.set_qss(btn, """
            QPushButton {{
                background:{btn}; color:{dim};
                border:1px solid {border};
                border-radius:3px; font-size:10px; font-weight:bold;
            }}
            """.format(**_C))

    def _refresh_vis_states(self):
        count = 0
        if hasattr(self, "hot_button_count_slider"):
            count = self.hot_button_count_slider.value()
        for i, btn in enumerate(getattr(self, "vis_toggle_buttons", [])):
            state = i < count
            btn.setChecked(state)
            self._style_vis(btn, state)

    def _on_hot_button_count_changed(self, value):
        self._refresh_vis_states()
        self.panel.set_quick_button_count(value, save=True)

    # Compatibility aliases for older callers. Visibility is now slider-owned.
    def _style_vis_toggle(self, btn, state):
        self._style_vis(btn, state)

    def _on_vis_toggle(self, idx, checked):
        self.hot_button_count_slider.setValue(idx + 1 if checked else idx)

    def _on_gap_changed(self, value):
        """Live-update icon button gap when the slider or spinbox changes."""
        self.panel.quick_button_gap = value
        if hasattr(self.panel, "quick_buttons_layout"):
            self.panel.quick_buttons_layout.setSpacing(value)
        if self.panel._ui_built and self.panel.isVisible():
            self.panel._resize_to_content()

    def _sync_layout_spacing_to_look(self, value):
        if 4 in self._loaded_tabs:
            self._look_draft["button_spacing"] = int(value)
            if hasattr(self, "look_value_controls"):
                ctl = self.look_value_controls.get("button_spacing")
                if ctl is not None and ctl.value() != int(value):
                    ctl.blockSignals(True)
                    ctl.setValue(int(value))
                    ctl.blockSignals(False)
    def _on_panel_scale_spin_changed(self, value):
        if hasattr(self, "panel_scale_slider"):
            self.panel_scale_slider.blockSignals(True)
            self.panel_scale_slider.setValue(int(round(value * 10)))
            self.panel_scale_slider.blockSignals(False)
        if 4 in self._loaded_tabs:
            self._look_draft["visual_scale"] = float(value)
            if hasattr(self, "look_value_controls"):
                ctl = self.look_value_controls.get("visual_scale")
                if ctl is not None and abs(ctl.value() - float(value)) > 1e-6:
                    ctl.blockSignals(True)
                    ctl.setValue(float(value))
                    ctl.blockSignals(False)
        self._apply_panel_scale_live(value)

    def _on_panel_scale_slider_changed(self, value):
        scale = value / 10.0
        if hasattr(self, "panel_scale_spin"):
            self.panel_scale_spin.blockSignals(True)
            self.panel_scale_spin.setValue(scale)
            self.panel_scale_spin.blockSignals(False)
        if 4 in self._loaded_tabs:
            self._look_draft["visual_scale"] = float(scale)
            if hasattr(self, "look_value_controls"):
                ctl = self.look_value_controls.get("visual_scale")
                if ctl is not None and abs(ctl.value() - float(scale)) > 1e-6:
                    ctl.blockSignals(True)
                    ctl.setValue(float(scale))
                    ctl.blockSignals(False)
        self._apply_panel_scale_live(scale)

    def _apply_panel_scale_live(self, scale):
        p = self.panel
        p.panel_scale = max(0.5, min(10.0, scale))
        p._apply_panel_scale()
        p._grid_dirty = True
        p.rebuild_grid()
        p.update_quick_buttons()
        if p._ui_built and p.isVisible():
            p._resize_to_content()

    def _on_hot_button_icon_scale_changed(self, value):
        """Scales the 10 hot buttons themselves (box+icon), the title bar's
        height (via _apply_panel_scale, which owns that sizing), and — since
        each hot button's own pie reads its size directly off the button's
        current width — their pie menus grow right along with it."""
        p = self.panel
        p.hot_button_icon_scale = max(0.5, min(3.0, value / 100.0))
        p._apply_panel_scale()
        p.update_quick_buttons()
        if p._ui_built and p.isVisible():
            p._resize_to_content()

    def _on_pie_icon_scale_changed(self, value):
        """Live-update the pie-menu icon scale when the slider or spinbox
        changes. No rebuild needed — pie widgets read pie_icon_scale fresh
        each time a pie is opened, so this takes effect on the very next
        hold."""
        self.panel.pie_icon_scale = value / 100.0

    def _on_hot_pie_icon_scale_changed(self, value):
        """Same as _on_pie_icon_scale_changed, but for the 10 hot buttons'
        own pies — kept independent from the panel-button pie icon scale."""
        self.panel.hot_pie_icon_scale = value / 100.0

    def _on_pie_hold_delay_changed(self, value):
        """Live-update how long a button must be held before its pie opens.
        0 = instant (opens immediately on press, no hold needed at all).
        No rebuild needed — read fresh from the panel on every press."""
        self.panel.pie_hold_delay_ms = value

    def _set_pie_dim_controls_enabled(self, enabled):
        for w in (getattr(self, "pie_dim_mode_combo", None),
                  getattr(self, "pie_dim_delay_slider", None),
                  getattr(self, "pie_dim_delay_spin", None),
                  getattr(self, "pie_dim_fade_slider", None),
                  getattr(self, "pie_dim_fade_spin", None),
                  getattr(self, "pie_dim_opacity_slider", None),
                  getattr(self, "pie_dim_opacity_spin", None)):
            if w is not None:
                w.setEnabled(enabled)

    def _on_pie_dim_toggled(self, checked):
        self.panel.pie_dim_enabled = checked
        self._set_pie_dim_controls_enabled(checked)

    def _on_pie_dim_mode_changed(self, index):
        self.panel.pie_dim_mode = "screen" if index == 1 else "panel"

    def _on_pie_dim_delay_changed(self, value):
        self.panel.pie_dim_delay_ms = value

    def _on_pie_dim_fade_changed(self, value):
        self.panel.pie_dim_fade_ms = value

    def _on_pie_dim_opacity_changed(self, value):
        self.panel.pie_dim_opacity = value

    def _on_pie_angle_changed(self, value):
        self.panel.pie_start_angle = float(value)


    # ── Apply ─────────────────────────────────────────────────────────────────
    def apply_changes(self):
        p = self.panel

        if 0 in self._loaded_tabs:
            p.panel_scale  = self.panel_scale_spin.value()
            p.cols         = self.cols_spin.value()
            p.button_scale = self.scale_spin.value()
            p.padding      = self.pad_spin.value()
            p.quick_alignment           = self.align_combo.currentIndex()
            p.grid_full_row_alignment   = self.grid_full_row_align_combo.currentIndex()
            p.grid_row_alignment        = self.grid_row_align_combo.currentIndex()
            p.quick_button_gap          = self.btn_gap_slider.value()
            p.hot_button_icon_scale     = self.hot_button_icon_scale_slider.value() / 100.0
            p.pie_icon_scale            = self.pie_icon_scale_slider.value() / 100.0
            p.hot_pie_icon_scale        = self.hot_pie_icon_scale_slider.value() / 100.0
            p.pie_hold_delay_ms         = self.pie_hold_delay_slider.value()
            p.pie_dim_enabled           = self.pie_dim_check.isChecked()
            p.pie_dim_mode              = "screen" if self.pie_dim_mode_combo.currentIndex() == 1 else "panel"
            p.pie_dim_delay_ms          = self.pie_dim_delay_slider.value()
            p.pie_dim_fade_ms           = self.pie_dim_fade_slider.value()
            p.pie_dim_opacity           = self.pie_dim_opacity_slider.value()
            p.pie_start_angle           = float(self.pie_angle_slider.value())
            p.close_on_click            = self.close_on_click_check.isChecked()
            p.search_always_on          = self.search_always_on_check.isChecked()
            p.recent_commands_enabled   = self.recent_commands_check.isChecked()
            p.node_detection_enabled    = self.node_detection_check.isChecked()

        if 1 in self._loaded_tabs:
            p.set_quick_button_count(self.hot_button_count_slider.value())

            for i in range(len(self.quick_name_edits)):
                d = p.custom_buttons[i]
                d["name"] = (self.quick_name_edits[i].text() or
                             "BTN{}".format(i + 1))[:6]
                d["tooltip"] = self.quick_tooltip_edits[i].text() or ""
                d["type"] = (
                    "python" if self.quick_type_boxes[i].currentIndex() == 1 else "mel")
                d["code"] = self.quick_code_edits[i].toPlainText() or ""
                d["invert_close_on_click"] = (
                    self.quick_close_override_checks[i].isChecked())
                d["visible"] = i < p.quick_button_count
                d["icon"] = (self._quick_icons[i]
                             if i < len(self._quick_icons) else d.get("icon", ""))
                p.quick_button_rc[i] = {
                    "name": self.quick_rc_name_edits[i].text().strip(),
                    "code": self.quick_rc_code_edits[i].toPlainText(),
                    "type": ("python" if self.quick_rc_type_boxes[i].currentIndex() == 0
                             else "mel"),
                    "icon": (self._quick_rc_icons[i]
                             if i < len(self._quick_rc_icons)
                             else p.quick_button_rc[i].get("icon", "")),
                }

        if 2 in self._loaded_tabs:
            p.panel_title = self.panel_title_edit.text().strip() or "ModPanel"
            p.title_click_code = self.title_click_edit.toPlainText()
            p.title_click_type = (
                "python" if self.title_click_type_box.currentIndex() == 0 else "mel")
            p.title_click_tooltip = self.title_click_tooltip_edit.text().strip()
            p.title_right_click_code = self.title_right_click_edit.toPlainText()
            p.title_right_click_type = (
                "python" if self.title_right_click_type_box.currentIndex() == 0 else "mel")
            p.title_right_click_tooltip = self.title_right_click_tooltip_edit.text().strip()
            p.title_double_click_code = self.title_double_click_edit.toPlainText()
            p.title_double_click_type = (
                "python" if self.title_double_click_type_box.currentIndex() == 0 else "mel")
            p.title_double_click_tooltip = self.title_double_click_tooltip_edit.text().strip()

        if 3 in self._loaded_tabs:
            ws_a = self.ws_a_combo.currentText().strip()
            ws_b = self.ws_b_combo.currentText().strip()
            if ws_a and ws_b:
                p.workspace_cycle = [ws_a, ws_b]
            uv_ws = self.uv_ws_combo.currentText().strip()
            if uv_ws:
                p.uv_tab_workspace = uv_ws

        if 4 in self._loaded_tabs:
            # Mirror values exposed on older tabs into the Look payload before
            # applying it, so whichever editor the user touched wins cleanly.
            if 0 in self._loaded_tabs:
                self._look_draft["visual_scale"] = self.panel_scale_spin.value()
                self._look_draft["button_spacing"] = self.pad_spin.value()
            if 2 in self._loaded_tabs:
                self._look_draft["title_text"] = (
                    self.panel_title_edit.text().strip() or "ModPanel")
            p.apply_look_settings(self._look_draft, save=False, refresh=False)

        p.tab_workspaces = {
            "uv": p.uv_tab_workspace,
            "node_detect": p.node_detection_enabled,
        }

        if hasattr(p, "_search_bar"):
            if p.search_always_on:
                p._search_bar.setVisible(True)
            elif not p._search_bar.hasFocus():
                p._search_bar.setVisible(False)
        if hasattr(p, "_update_recent_row"):
            p._update_recent_row()

        p._apply_panel_scale()
        p.rebuild_grid()
        p.update_quick_buttons()
        p.save_tab_config(p.current_tab)
        p.save_global_state()

        self.settingsChanged.emit()
        self.accept()

    # ── Import / Export / Delete ──────────────────────────────────────────────
    def _import_config(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import ModPanel Preset", "",
            "ModPanel Preset (*.json)"
        )
        if not path:
            return
        try:
            import json
            with open(path, "r") as f:
                cfg = json.load(f)
        except Exception as e:
            try:
                import maya.cmds as _mc;  _mc.warning("Import failed (read): {}".format(e))
            except Exception:
                pass
            return

        choices = self._show_import_choices(cfg)
        if choices is None:
            return   # user cancelled

        try:
            self.panel.import_all_tabs(cfg, choices)
            self.refresh_from_panel()
            self.settingsChanged.emit()
        except Exception as e:
            try:
                import maya.cmds as _mc;  _mc.warning("Import failed (apply): {}".format(e))
            except Exception:
                pass

    def _export_config(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export ModPanel Preset",
            "phoenix_panel_preset.json",
            "ModPanel Preset (*.json)"
        )
        if not path:
            return
        try:
            import json
            with open(path, "w") as f:
                json.dump(self.panel.export_all_tabs(), f, indent=2)
        except Exception as e:
            try:
                import maya.cmds as _mc;  _mc.warning("Export failed: {}".format(e))
            except Exception:
                pass

    def _delete_all_confirm(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Delete All Buttons",
            "Delete every button in the current panel?\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        self.panel.buttons_data = []
        self.panel.save_tab_config(self.panel.current_tab)
        self.panel.rebuild_grid()
        self.settingsChanged.emit()

    def _reset_all_confirm(self):
        """Full factory reset — all panels, hot buttons, and title codes."""
        reply = QtWidgets.QMessageBox.question(
            self, "Reset Everything",
            "This will permanently clear:\n\n"
            "  \u2022  All buttons in all 7 panels\n"
            "  \u2022  All 5 hot button configurations\n"
            "  \u2022  All title middle-click and right-click codes\n\n"
            "This cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        self.panel.reset_all()
        self.settingsChanged.emit()
        self.close()   # close settings so the user sees the clean panel immediately
