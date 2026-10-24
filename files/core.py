# -*- coding: utf-8 -*-
"""Main PhoenixPanel dialog - 3-tab system, right-click title to cycle tabs.

Tab assignment logic:
  Tab 0  – General (all workspaces not caught by tabs 1/2)
  Tab 1  – UV Editing workspace (auto-switch when UV Editor layout active)
  Tab 2  – Hypershade (auto-switch when Hypershade panel is the active panel)

Right-clicking the "PhoenixPanel" title label cycles through the 3 tabs.
There is no hover-reveal tab bar; the only UI for tabs is the three thin
indicator segments drawn below the title row.
"""

from __future__ import annotations

import os
import json
import html

import maya.cmds as cmds
import maya.mel as mel

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from . import theme as _theme

NUM_TABS = 3
NUM_HIDDEN_TABS = 3                        # Q / W / E hidden panels
_TOTAL_TABS = NUM_TABS + NUM_HIDDEN_TABS   # 6 total slots
NUM_QUICK_BTNS = 10                        # icon hot-buttons in the title bar
MAX_PIE_COMMANDS = 6                       # max radial pie-menu items per button


def _render_glyph_icon(glyph, size, color_hex):
    """Paint a single glyph centered in a size x size transparent pixmap and
    return it as a QIcon.

    Used instead of just setting text on a QPushButton for tiny glyph-only
    buttons (the pin icon): QPushButton centers TEXT using the font's
    advance-width box, which for some symbol glyphs doesn't match their
    visual bounding box, so text-align:center plus padding tweaks never
    reliably centered it — and any fixed-pixel padding correction breaks
    again the moment the button is a different size (i.e. panel_scale != 1).
    Painting it ourselves with QPainter.drawText(rect, AlignCenter, glyph)
    centers the glyph's actual drawn bounds within the pixmap, which stays
    correct at any size since we recompute it fresh whenever size changes.
    """
    size = max(1, int(size))
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    try:
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
    except Exception:
        pass
    font = p.font()
    font.setPixelSize(max(6, int(size * 0.62)))
    p.setFont(font)
    p.setPen(QtGui.QColor(color_hex))
    p.drawText(QtCore.QRectF(0, 0, size, size), QtCore.Qt.AlignCenter, glyph)
    p.end()
    return QtGui.QIcon(pm)


# ---------------------------------------------------------------------------
# Look/theme defaults
# ---------------------------------------------------------------------------
# Fresh installs default to the ModPanel style (black surfaces, thin outlines,
# small radii). The original palette lives on as the "classic" preset in
# theme.LOOK_PRESETS. The three layout-adjacent values are mirrored to the
# existing panel properties for backward compatibility:
#   title_text     <-> panel_title
#   visual_scale   <-> panel_scale
#   button_spacing <-> padding
DEFAULT_LOOK = {
    "title_text":       "ModPanel",
    "panel_background": "#000000",
    "panel_border":     "#2b2b2b",
    "title_bar":        "#000000",
    "button":           "#0c0c0c",
    "button_hover":     "#141414",
    "button_pressed":   "#050505",
    "button_selected":  "#071018",
    "text":             "#f2f2f2",
    "icon":             "#d0d0d0",
    "accent":           "#46b6ff",
    "opacity":          100,
    "border_thickness": 1,
    "corner_radius":    6,
    "button_padding":   6,
    "button_spacing":   8,
    "visual_scale":     1.0,
}

_LOOK_COLOR_KEYS = (
    "panel_background", "panel_border", "title_bar", "button",
    "button_hover", "button_pressed", "button_selected", "text",
    "icon", "accent",
)


def _is_hex_colour(value):
    if not isinstance(value, str):
        return False
    value = value.strip()
    if len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
        return True
    except (TypeError, ValueError):
        return False


def normalize_look(raw=None):
    """Return a validated, complete Look dictionary.

    Unknown keys are ignored and malformed values fall back individually, so
    presets from future versions or hand-edited JSON cannot break panel load.
    """
    src = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULT_LOOK)
    for key in _LOOK_COLOR_KEYS:
        value = src.get(key)
        if _is_hex_colour(value):
            out[key] = value.strip().lower()

    title = src.get("title_text")
    if isinstance(title, str) and title.strip():
        out["title_text"] = title.strip()[:80]

    def _int(key, low, high):
        try:
            return max(low, min(high, int(src.get(key, out[key]))))
        except (TypeError, ValueError):
            return out[key]

    def _float(key, low, high):
        try:
            return max(low, min(high, float(src.get(key, out[key]))))
        except (TypeError, ValueError):
            return out[key]

    out["opacity"] = _int("opacity", 20, 100)
    out["border_thickness"] = _int("border_thickness", 0, 8)
    out["corner_radius"] = _int("corner_radius", 0, 32)
    out["button_padding"] = _int("button_padding", 0, 18)
    out["button_spacing"] = _int("button_spacing", 0, 50)
    out["visual_scale"] = _float("visual_scale", 0.1, 10.0)
    return out


def _rgba_css(hex_colour, opacity_percent):
    """Convert #RRGGBB + percentage to a Qt stylesheet rgba() string."""
    colour = hex_colour if _is_hex_colour(hex_colour) else DEFAULT_LOOK["panel_background"]
    alpha = max(0, min(255, int(round(float(opacity_percent) * 2.55))))
    return "rgba({},{},{},{})".format(
        int(colour[1:3], 16), int(colour[3:5], 16),
        int(colour[5:7], 16), alpha)


def _sanitize_pie_commands(raw):
    """Validate/normalise a raw ``pie_commands`` value from JSON (or live
    UI state) into a list of at most MAX_PIE_COMMANDS well-formed dicts.
    Malformed entries are skipped rather than raising, so a corrupt or
    hand-edited config file can never fail the whole load. Missing keys
    default safely; anything beyond the max is dropped (callers that need
    to warn the user about truncation should compare lengths themselves)."""
    if not isinstance(raw, list):
        return []
    out = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        code = (entry.get("code") or "")
        if not isinstance(code, str):
            continue
        icon_candidates = []
        raw_candidates = entry.get("icon_candidates", [])
        if isinstance(raw_candidates, (list, tuple)):
            for candidate in raw_candidates:
                candidate = str(candidate or "").strip()
                if candidate and candidate not in icon_candidates:
                    icon_candidates.append(candidate)
        icon_name = str(entry.get("icon", "") or "")
        if icon_name and icon_name not in icon_candidates:
            icon_candidates.append(icon_name)
        out.append({
            "name":    str(entry.get("name", "") or ""),
            "tooltip": str(entry.get("tooltip", "") or ""),
            "type":    "python" if str(entry.get("type", "mel") or "mel").lower() == "python" else "mel",
            "code":    code,
            "icon":    icon_name,
            "icon_candidates": icon_candidates,
        })
        if len(out) >= MAX_PIE_COMMANDS:
            break
    return out


def _do_phoenix_panel_reload(reopen=True):
    """Hot-reload every PhoenixPanel module and reopen a fresh instance —
    the exact same steps as update-it.ini, just triggered by double-clicking
    the title instead of running the script manually.

    This is a plain module-level function (not a bound method) deliberately
    called via QTimer.singleShot(0, ...) rather than directly from whatever
    method is handling the double-click: that defers execution to the next
    idle tick, so by the time this actually runs, no PhoenixPanel method
    (including this very call) is still on the call stack — reloading
    core.py itself while one of its own methods is mid-execution is the
    kind of thing that works by luck rather than by design.
    """
    import importlib
    import sys

    try:
        import phoenix_panel.launcher as _launcher
    except Exception:
        return

    if _launcher._WINDOW_INSTANCE is not None:
        try:
            if hasattr(_launcher._WINDOW_INSTANCE, "_cancel_all_active_pies"):
                _launcher._WINDOW_INSTANCE._cancel_all_active_pies()
        except Exception:
            pass
        try:
            _launcher._WINDOW_INSTANCE.close()
            _launcher._WINDOW_INSTANCE.deleteLater()
        except Exception:
            pass
        _launcher._WINDOW_INSTANCE = None

    # Belt-and-suspenders: release any dangling mouse grab (e.g. a pie menu
    # that somehow outlived the panel) before tearing anything down.
    try:
        _app = QtWidgets.QApplication.instance()
        if _app is not None:
            grabber = QtWidgets.QWidget.mouseGrabber()
            if grabber is not None:
                grabber.releaseMouse()
    except Exception:
        pass

    _BASE = "phoenix_panel"
    _MODULES = ["theme", "utils", "widgets", "shelf_picker", "pie_editor", "settings", "core", "launcher"]
    for _mod in _MODULES:
        _full = "{}.{}".format(_BASE, _mod)
        if _full in sys.modules:
            try:
                importlib.reload(sys.modules[_full])
            except Exception:
                cmds.warning("ModPanel: reload of {} failed".format(_full))

    if _BASE in sys.modules:
        try:
            importlib.reload(sys.modules[_BASE])
        except Exception:
            pass

    try:
        import phoenix_panel.core as _core
        _core._SHELF_PICKER = None
        _core._SETTINGS = None
    except Exception:
        pass

    try:
        import phoenix_panel.utils as _utils
        _utils.clear_icon_cache()
        _utils._MAYA_MAIN_WINDOW = None
    except Exception:
        pass

    if reopen:
        try:
            import phoenix_panel
            phoenix_panel.open_phoenix_panel()
        except Exception:
            cmds.warning("ModPanel: reload finished but reopening the panel failed")


# Workspace name fragments that identify the UV Editing layout in Maya.
# Maya's built-in UV Editing workspace is usually called "UV Editing".
_UV_WORKSPACE_HINTS = ("uv editing", "uv editor", "uv edit")

# Shader / material node types that imply the user is working in Hypershade.
_SHADER_NODE_TYPES = frozenset({
    "lambert", "blinn", "phong", "phongE", "anisotropic",
    "rampShader", "layeredShader", "surfaceShader", "useBackground",
    "hairTubeShader", "shadingEngine", "displacementShader",
    "file", "place2dTexture", "place3dTexture", "bump2d",
    "aiStandardSurface", "aiLambert", "aiBlinn", "aiPhong", "aiFlat",
    "RedshiftMaterial", "RedshiftShaderSwitch",
    "VRayMtl", "VRayLightMtl", "VRayBlendMtl",
    "StingrayPBS",
})

# Lazy imports - only load when needed
_SHELF_PICKER = None
_SETTINGS = None


def _get_shelf_picker():
    global _SHELF_PICKER
    if _SHELF_PICKER is None:
        from .shelf_picker import ShelfPickerDialog
        _SHELF_PICKER = ShelfPickerDialog
    return _SHELF_PICKER


def _get_settings():
    global _SETTINGS
    if _SETTINGS is None:
        from .settings import PhoenixPanelSettings   # re-imported after each reload
        _SETTINGS = PhoenixPanelSettings
    return _SETTINGS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_hypershade_active():
    """Return True if the cursor is over a Hypershade window, or Hypershade is active.

    widgetAt() misses OpenGL viewports, so we walk ALL top-level windows and
    check if any Hypershade window's frameGeometry contains the cursor.
    """
    try:
        try:
            from PySide6 import QtWidgets as _QW, QtGui as _QG
        except ImportError:
            from PySide2 import QtWidgets as _QW, QtGui as _QG

        cursor_pos = _QG.QCursor.pos()

        for win in _QW.QApplication.topLevelWidgets():
            if not win.isVisible():
                continue
            title = win.windowTitle().lower()
            if "hypershade" not in title:
                continue
            # Cursor is inside this Hypershade window
            if win.frameGeometry().contains(cursor_pos):
                return True
            # Or it is the active window (keyboard shortcut trigger)
            if win.isActiveWindow():
                return True

        # Fallback: Maya panel focus (docked Hypershade)
        focused = cmds.getPanel(withFocus=True) or ""
        if focused and cmds.getPanel(typeOf=focused) == "hyperShadePanel":
            return True

    except Exception:
        pass
    return False


def _detect_desired_tab(tab_workspaces=None):
    """Return the main tab index (0/1/2) appropriate for the current Maya state.

    Priority:
      1. If Hypershade is the active window  → tab 2
      2. If the workspace matches the configured UV workspace → tab 1
      3. Everything else                      → tab 0

    tab_workspaces: dict with optional "uv" key carrying the user-configured
    workspace name that should trigger tab 1.  When absent, falls back to the
    built-in _UV_WORKSPACE_HINTS strings.
    """
    # --- Hypershade check (multi-strategy) ---
    if _is_hypershade_active():
        return 2

    # --- UV workspace check ---
    try:
        workspace_name = (cmds.workspaceLayoutManager(
            query=True, current=True) or "").strip()
        ws_lower = workspace_name.lower()

        if tab_workspaces and isinstance(tab_workspaces, dict):
            # User-configured: exact name match (case-insensitive)
            uv_ws = (tab_workspaces.get("uv") or "").strip()
            if uv_ws and ws_lower == uv_ws.lower():
                return 1
        else:
            # No config yet — fall back to built-in hints
            if any(hint in ws_lower for hint in _UV_WORKSPACE_HINTS):
                return 1
    except Exception:
        pass

    # --- Node-type detection: selected shaders → Hypershade tab ---
    node_detect = True
    if tab_workspaces and isinstance(tab_workspaces, dict):
        node_detect = bool(tab_workspaces.get("node_detect", True))
    if node_detect:
        try:
            sel = cmds.ls(sl=True) or []
            for obj in sel[:10]:
                try:
                    if cmds.objectType(obj) in _SHADER_NODE_TYPES:
                        return 2
                except Exception:
                    continue
        except Exception:
            pass

    return 0


# ---------------------------------------------------------------------------
# _QuickToolButton
# ---------------------------------------------------------------------------
# The 10 quick buttons previously relied on the app-wide eventFilter to catch
# right-clicks (same trick used for the title label / add_btn / settings_btn).
# In practice that chain doesn't reliably deliver right-click presses for
# these buttons, so instead we override mousePressEvent directly on the
# button itself — this is the widget's own primary event handler and is
# guaranteed to run once the event reaches the widget at all (which it does,
# since left-click already works reliably), with no dependency on filter
# install order, object identity checks, or exceptions elsewhere in the
# shared eventFilter.
#
# Hold-to-open pie support follows the same precedent: implemented as direct
# mousePress/Release overrides rather than an installEventFilter(), for the
# same reliability reason. Buttons with no pie_commands configured fall
# straight through to super() exactly as before — zero behavioural change.
class _QuickToolButton(QtWidgets.QToolButton):
    rightClicked = QtCore.Signal(QtCore.QPoint)
    # Emitted when a pie command is chosen (release over a pie item)
    pieCommandTriggered = QtCore.Signal(dict)
    # Emitted on a short left-click when pie_commands ARE configured (native
    # `clicked` never fires in that case since we own the whole press/release
    # ourselves — see mousePressEvent below).
    leftClickTriggered = QtCore.Signal()

    # Fallback used only if the panel (or its pie_hold_delay_ms attribute)
    # can't be reached for some reason — normal path reads the live,
    # user-configurable value via self.window().pie_hold_delay_ms.
    HOLD_THRESHOLD_MS = 100

    def __init__(self, parent=None):
        super(_QuickToolButton, self).__init__(parent)
        self.pie_provider  = None   # callable() -> list[dict], set externally
        self.icon_resolver = None   # callable(icon_name) -> QIcon
        self.angle_provider = None  # callable() -> float or None (per-button pie rotation override)
        self._press_button = None
        self._active_pie   = None

        self._hold_timer = QtCore.QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_timeout)

    def _pie_commands(self):
        if not self.pie_provider:
            return []
        try:
            cmds = self.pie_provider() or []
        except Exception:
            cmds = []
        return [c for c in cmds if isinstance(c, dict) and (c.get("code") or "").strip()][:6]

    def mousePressEvent(self, event):
        panel = self.window()
        if getattr(panel, "_reposition_mode", False):
            super(_QuickToolButton, self).mousePressEvent(event)
            return

        if event.button() == QtCore.Qt.RightButton:
            self.rightClicked.emit(event.pos())
            event.accept()
            return

        if event.button() == QtCore.Qt.LeftButton:
            if self._pie_commands():
                self._press_button = QtCore.Qt.LeftButton
                delay = getattr(panel, "pie_hold_delay_ms", self.HOLD_THRESHOLD_MS)
                self._hold_timer.start(max(0, int(delay)))
                event.accept()
                return

        super(_QuickToolButton, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._press_button is not None and event.button() == self._press_button:
            was_pending = self._hold_timer.isActive()
            self._hold_timer.stop()
            self._press_button = None
            if not was_pending:
                # Hold already fired — pie (or a no-op) handled everything.
                event.accept()
                return
            if self.rect().contains(event.pos()):
                self.leftClickTriggered.emit()
            event.accept()
            return
        super(_QuickToolButton, self).mouseReleaseEvent(event)

    def _on_hold_timeout(self):
        panel = self.window()
        if getattr(panel, "_reposition_mode", False):
            return
        cmds = self._pie_commands()
        if not cmds:
            return
        self._open_pie(cmds)

    def _open_pie(self, cmds):
        from .widgets import PieMenuWidget
        from .utils import get_maya_main_window
        global_center = self.mapToGlobal(self.rect().center())
        src_size  = self.width()
        icon_scale = max(0.5, min(1.5, getattr(self.window(), "hot_pie_icon_scale", 1.0)))
        base_item_size = max(18, min(int(src_size * 0.9), 100))
        item_size = max(14, min(int(round(base_item_size * icon_scale)), 160))
        resolver  = self.icon_resolver or (lambda name: QtGui.QIcon())
        try:
            parent_win = get_maya_main_window()
        except Exception:
            parent_win = None

        dim_settings = self._build_dim_settings(global_center, src_size)
        override_angle = None
        if self.angle_provider is not None:
            try:
                override_angle = self.angle_provider()
            except Exception:
                override_angle = None
        start_angle = (override_angle if override_angle is not None
                       else getattr(self.window(), "pie_start_angle", -90.0))

        popup = PieMenuWidget(global_center, src_size, cmds, item_size, resolver,
                               parent=parent_win, dim_settings=dim_settings,
                               start_angle=start_angle)
        popup.commandSelected.connect(self._on_pie_selected)
        popup.cancelled.connect(self._on_pie_cancelled)
        self._active_pie = popup
        self._apply_origin_glow()
        popup.start()

    def _build_dim_settings(self, source_global_center, source_size):
        panel = self.window()
        if not getattr(panel, "pie_dim_enabled", True):
            return {"enabled": False}
        try:
            from .utils import compute_pie_dim_rect
            mode = getattr(panel, "pie_dim_mode", "panel")
            dim_rect = compute_pie_dim_rect(panel, mode)
        except Exception:
            dim_rect = None
        if dim_rect is None:
            return {"enabled": False}
        half = source_size / 2.0
        source_rect = QtCore.QRect(
            int(source_global_center.x() - half), int(source_global_center.y() - half),
            int(source_size), int(source_size))
        opacity_pct = getattr(panel, "pie_dim_opacity", 55)
        return {
            "enabled":  True,
            "dim_rect": dim_rect,
            "source_rect": source_rect,
            "source_radius": max(0, min(12, int(
                self._look()["corner_radius"] * 0.45))),
            "delay_ms": getattr(panel, "pie_dim_delay_ms", 150),
            "fade_ms":  getattr(panel, "pie_dim_fade_ms", 200),
            "opacity":  max(0.1, min(1.0, opacity_pct / 100.0)),
        }

    def _look(self):
        panel = self.window()
        return normalize_look(getattr(panel, "look_theme", None))

    def _apply_origin_glow(self):
        # Stylesheet glow stays rounded and follows the current Look theme.
        look = self._look()
        radius = max(0, min(12, int(look["corner_radius"] * 0.45)))
        _theme.set_qss_look(self, """
        QToolButton {{
            background: {selected};
            color: {icon};
            border-radius: {radius}px;
            border: 2px solid {accent};
            padding: {padding}px;
        }}
        """.format(selected=look["button_selected"], icon=look["icon"],
                   radius=radius, accent=look["accent"],
                   padding=max(0, int(look["button_padding"] * 0.35))))

    def _clear_origin_glow(self):
        self._normal_style()

    def _normal_style(self):
        look = self._look()
        radius = max(0, min(12, int(look["corner_radius"] * 0.45)))
        border = max(0, min(3, int(look["border_thickness"])))
        _theme.set_qss_look(self, """
        QToolButton {{
            background: {button};
            color: {icon};
            border-radius: {radius}px;
            border: {border}px solid {panel_border};
            padding: {padding}px;
        }}
        QToolButton:hover {{ background: {hover}; border-color: {accent}; }}
        QToolButton:pressed {{ background: {pressed}; }}
        """.format(button=look["button"], icon=look["icon"],
                   radius=radius, border=border, panel_border=look["panel_border"],
                   padding=max(0, int(look["button_padding"] * 0.35)),
                   hover=look["button_hover"], accent=look["accent"],
                   pressed=look["button_pressed"]))

    def _on_pie_selected(self, cmd):
        self._active_pie = None
        self._clear_origin_glow()
        self.pieCommandTriggered.emit(cmd)

    def _on_pie_cancelled(self):
        self._active_pie = None
        self._clear_origin_glow()

    def cancel_active_pie(self):
        if self._active_pie is not None:
            try:
                self._active_pie.cancel_now()
            except Exception:
                pass
            self._active_pie = None


# ---------------------------------------------------------------------------
# PhoenixPanel
# ---------------------------------------------------------------------------

class PhoenixPanel(QtWidgets.QDialog):
    """Floating popup grid of custom shelf buttons with 3-tab system."""

    MARGIN = 16  # minimum screen padding

    # ----------------------------------------------------------------
    # Keyboard shortcut map  key → tab index.
    # Main panels  : 1/2/3  → tabs 0/1/2
    # Hidden panels: Q/W/E → tabs 3/4/5
    # Add a new entry here to expose additional panels or remap keys.
    # ----------------------------------------------------------------
    _SHORTCUT_MAP = {
        QtCore.Qt.Key_1: 0,
        QtCore.Qt.Key_2: 1,
        QtCore.Qt.Key_3: 2,
        QtCore.Qt.Key_Q: NUM_TABS + 0,   # hidden panel 1
        QtCore.Qt.Key_W: NUM_TABS + 1,   # hidden panel 2
        QtCore.Qt.Key_E: NUM_TABS + 2,   # hidden panel 3
    }

    # Labels shown in the title bar when a hidden panel is active.
    _HIDDEN_TAB_LABELS = ["Q", "W", "E"]

    def __init__(self, parent=None):
        super(PhoenixPanel, self).__init__(parent)

        from .utils import (get_config_path, resolve_maya_icon, sized_icon,
                            resolve_maya_icon_candidates, sized_icon_candidates,
                            shelf_button_icon_names)
        from .widgets import PhoenixButtonWidget

        self._resolve_maya_icon             = resolve_maya_icon
        self._sized_icon                    = sized_icon
        self._resolve_maya_icon_candidates  = resolve_maya_icon_candidates
        self._sized_icon_candidates         = sized_icon_candidates
        self._shelf_button_icon_names       = shelf_button_icon_names
        self._PhoenixButtonWidget  = PhoenixButtonWidget
        self._get_config_path      = get_config_path

        self.setObjectName("PhoenixPanel")
        self.setWindowTitle("ModPanel")

        flags = (
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(50, 50)
        self.setAcceptDrops(True)
        # Accept keyboard focus so shortcuts fire without a click
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        # ---- Tab state ----
        self.current_tab = 0                 # 0, 1 or 2
        self.config_base_path = get_config_path().replace(".json", "")

        # ---- Free Stuff (Tab key) view state ----
        self._free_stuff_active = False
        self._free_stuff_saved_buttons = None

        # ---- Per-tab UI state (loaded from disk) ----
        self._reset_tab_state()

        self.button_widgets   = []
        self.quick_buttons    = []

        # Right-click actions for quick buttons — shared across all tabs
        # Loaded/saved in global config, not per-tab
        self.quick_button_rc = [
            {"name": "", "code": "", "type": "python", "icon": ""}
            for _ in range(NUM_QUICK_BTNS)
        ]

        # Hot buttons — shared across ALL tabs (loaded from global config)
        self.custom_buttons = [
            {"name": "BTN{}".format(i + 1), "tooltip": "",
             "type": "mel", "code": "", "icon": "", "visible": False,
             "invert_close_on_click": False, "pie_commands": []}
            for i in range(NUM_QUICK_BTNS)
        ]

        # Layout settings — shared across ALL panels, persisted in global config.
        self.cols                    = 4
        self.button_scale            = 1.0
        self.panel_scale              = 1.0   # master multiplier for the WHOLE panel, 0.1-10.0
        self.padding                 = 8
        self.quick_alignment         = 2
        self.grid_full_row_alignment = 1
        self.grid_row_alignment      = 1
        self.close_on_click          = True   # command buttons close panel by default
        self.search_always_on        = False
        self.recent_commands_enabled = True
        self.recent_commands         = []
        self.node_detection_enabled  = True
        self._pinned                 = False
        self._search_was_active      = False
        self.quick_button_gap        = 4      # px gap between the 10 icon hot-buttons
        self.quick_button_count      = 0      # first N hot buttons are shown
        self.pie_icon_scale          = 1.0    # icon size within each pie-menu item (0.5-1.5) — panel buttons
        self.hot_pie_icon_scale      = 1.0    # same, but for the 10 hot buttons' own pies (independent)
        self.hot_button_icon_scale   = 1.0    # scales the 10 hot buttons themselves (box+icon+title-bar height)
        self.pie_hold_delay_ms       = 100    # ms to hold before the pie opens (0 = instant)
        self.pie_dim_enabled         = True   # dim background while a pie is open
        self.pie_dim_mode            = "panel"  # "panel" | "screen"
        self.pie_dim_delay_ms        = 150    # ms after the pie opens before dimming starts
        self.pie_dim_fade_ms         = 200    # ms for the dim fade-in itself
        self.pie_dim_opacity         = 55     # how dark the dim gets, 10-100 (%)
        self.pie_start_angle         = -90.0  # degrees; where the first pie item sits (-90 = top)
        self.panel_title             = "ModPanel"
        self.look_theme              = normalize_look()
        self._shelf_drop_widget      = None   # native drop-target bridge (see _setup_shelf_drop_zone)
        self._shelf_drop_window      = None   # its hidden host window name

        # Workspace pair cycled by right-clicking the ⚙ Settings button.
        self.workspace_cycle = ["General", "UV Editing"]

        # Workspace that triggers Tab 1 (UV panel) auto-switch.
        self.uv_tab_workspace = "UV Editing"
        # Passed to _detect_desired_tab so it uses the configured workspace + node flags.
        self.tab_workspaces = {"uv": self.uv_tab_workspace, "node_detect": True}

        # Reposition mode (panel-owned drag state)
        self._reposition_mode  = False
        self._drag_src_index   = None
        self._drag_dst_index   = None
        self._drag_ghost       = None
        self._drag_timer       = None
        self._ignore_close    = False
        self._window_drag_pos  = None   # used for pinned-mode window dragging
        self._event_filters_installed = []

        # ---- Workspace monitoring ----
        self._workspace_poll_timer = None   # QTimer for lightweight polling

        # Load last-used tab then load that tab's config.
        self.load_global_state()
        self.load_tab_config(self.current_tab)

        self._ui_built      = False
        self._grid_dirty    = True   # True = grid needs rebuild before next show

    # ------------------------------------------------------------------
    # Default state values (one tab's worth)
    # ------------------------------------------------------------------
    def _reset_tab_state(self):
        """Reset only truly per-tab state. Layout settings live in global config."""
        self.buttons_data           = []
        self.title_click_code       = ""
        self.title_click_type       = "python"
        self.title_right_click_code = ""
        self.title_right_click_type = "python"
        self.title_double_click_code = ""
        self.title_double_click_type = "python"
        self.title_click_tooltip          = ""
        self.title_right_click_tooltip    = ""
        self.title_double_click_tooltip   = ""

    @staticmethod
    def _icon_semantic_text(info):
        if not isinstance(info, dict):
            return ""
        return "{} {} {} {} {}".format(
            info.get("name", ""), info.get("label", ""),
            info.get("annotation", ""), info.get("tooltip", ""),
            info.get("command", info.get("code", "")))

    @staticmethod
    def _icon_candidate_names(info, explicit_icon=None):
        names = []
        if isinstance(info, dict):
            raw = info.get("icon_candidates", [])
            if isinstance(raw, (list, tuple)):
                for name in raw:
                    name = str(name or "").strip()
                    if name and name not in names:
                        names.append(name)
            for key in ("image3", "image2", "image1", "image", "icon"):
                name = str(info.get(key, "") or "").strip()
                if name and name not in names:
                    names.append(name)
        if explicit_icon:
            name = str(explicit_icon).strip()
            if name and name not in names:
                names.insert(0, name)
        return names

    def _resolve_info_icon(self, info, size=None, explicit_icon=None):
        names = self._icon_candidate_names(info, explicit_icon=explicit_icon)
        semantic = self._icon_semantic_text(info)
        if size is None:
            return self._resolve_maya_icon_candidates(names, semantic)
        return self._sized_icon_candidates(names, size, semantic)

    def _resolve_pie_icon(self, icon_name, command_data=None):
        data = command_data if isinstance(command_data, dict) else {}
        names = self._icon_candidate_names(data, explicit_icon=icon_name)
        return self._resolve_maya_icon_candidates(
            names, self._icon_semantic_text(data))

    # ------------------------------------------------------------------
    # Lazy UI build
    # ------------------------------------------------------------------
    def _ensure_ui_built(self):
        if self._ui_built:
            return
        self._ui_built = True
        self._build_ui()
        self._apply_panel_scale()
        self.rebuild_grid()
        self._grid_dirty = False  # just built, clean
        self.update_quick_buttons()
        self._setup_shelf_drop_zone()

        from .utils import get_maya_main_window
        main_win = get_maya_main_window()
        if main_win:
            main_win.installEventFilter(self)
            self._event_filters_installed.append(main_win)

        self.installEventFilter(self)

        app = QtWidgets.QApplication.instance()
        if app:
            app.installEventFilter(self)
            self._event_filters_installed.append(app)

    # ------------------------------------------------------------------
    # Event filter  (outside-click to close + right-click title)
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        # Reposition mode intercepts ALL mouse events app-wide (both idle and drag)
        if self._reposition_mode:
            if self._reposition_event_filter(event):
                return True

        # ── App-level keyboard shortcuts ──────────────────────────────────────
        # The app-level filter means we get here BEFORE Maya's hotkey system
        # can consume 1/2/3/Q/W/E/R/X/Escape, which is what we want.
        #
        # IMPORTANT: this filter runs for every keypress in the whole app
        # (it's installed on QApplication), so `isVisible()` alone is not
        # enough — a pinned panel is visible all the time, which used to
        # swallow 1/2/3 even while the user was working in the viewport
        # (e.g. Maya's smooth-preview shortcut "3"). Gate on isActiveWindow()
        # too, so shortcuts are only intercepted when the panel genuinely
        # has OS keyboard focus — right after launch, or after the user
        # explicitly clicks on it — and Maya gets its keys back the moment
        # focus moves elsewhere, pinned or not.
        if (event.type() == QtCore.QEvent.KeyPress and self.isVisible()
                and self.isActiveWindow()):
            if not event.isAutoRepeat():
                key    = event.key()
                search = hasattr(self, "_search_bar") and self._search_bar.isVisible()

                # When the search bar has keyboard focus, only intercept Escape
                focused = QtWidgets.QApplication.focusWidget()
                if search and isinstance(focused, QtWidgets.QLineEdit):
                    if key == QtCore.Qt.Key_Escape:
                        self._hide_search()
                        return True
                    return False   # let the QLineEdit receive the typed character

                # Escape → close panel (unless pinned)
                if key == QtCore.Qt.Key_Escape and not self._pinned:
                    self.hide()
                    return True

                # X → show search bar
                if key == QtCore.Qt.Key_X:
                    if not getattr(self, "search_always_on", False):
                        self._show_search()
                    return True

                # 1/2/3 / Q/W/E/R → switch panel
                tab_index = self._SHORTCUT_MAP.get(key)
                if tab_index is not None:
                    self._switch_and_resize(tab_index)
                    return True

            return False

        # Search bar — legacy per-widget Escape fallback (kept for safety)
        if hasattr(self, "_search_bar") and obj is self._search_bar:
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self._hide_search()
                    return True

        # Title label: right-click cycles tab (or runs custom code), middle
        # runs custom code, left-click starts window drag when pinned,
        # double-click runs custom code or resets/reloads the panel
        # (same steps as update-it.ini) if none is configured
        if hasattr(self, "_title_label") and obj is self._title_label:
            if event.type() == QtCore.QEvent.MouseButtonDblClick:
                if event.button() == QtCore.Qt.LeftButton:
                    # Always route through the title action wrapper so the
                    # global Close on click rule also applies to the built-in
                    # reload action when no custom double-click code exists.
                    self._run_title_double_click_code()
                    return True
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.LeftButton and self._pinned:
                    try:
                        gp = event.globalPos()
                    except AttributeError:
                        gp = event.globalPosition().toPoint()
                    self._window_drag_pos = gp - self.frameGeometry().topLeft()
                    return True
                if event.button() == QtCore.Qt.RightButton:
                    # Same wrapper handles either the user command or the
                    # built-in panel-cycle action, including Close on click.
                    self._run_title_right_click_code()
                    return True
                if event.button() == QtCore.Qt.MiddleButton:
                    self._run_title_click_code()
                    return True

        # Right-click on + Shelf → toggle default material
        if hasattr(self, "add_btn") and obj is self.add_btn:
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.RightButton:
                    self._toggle_default_material()
                    return True

        # Right-click on ⚙ Settings → toggle UV / General workspace
        if hasattr(self, "settings_btn") and obj is self.settings_btn:
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.RightButton:
                    self._toggle_workspace()
                    return True

        # Pinned window drag — move the panel when dragging from the title label
        if (self._pinned and
                hasattr(self, "_window_drag_pos") and
                self._window_drag_pos is not None):
            if event.type() == QtCore.QEvent.MouseMove:
                if event.buttons() & QtCore.Qt.LeftButton:
                    try:
                        gp = event.globalPos()
                    except AttributeError:
                        gp = event.globalPosition().toPoint()
                    self.move(gp - self._window_drag_pos)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.LeftButton:
                    self._window_drag_pos = None

        # Outside-click dismiss — catches MouseButtonPress from app filter.
        # Also works when a button-launched floating window is active.
        if event.type() == QtCore.QEvent.MouseButtonPress:
            if not self.isVisible():
                return False
            if self._ignore_close:
                return False
            if self._reposition_mode:
                return False
            if self._pinned:
                return False

            try:
                gp = event.globalPos()
            except Exception:
                try:
                    gp = obj.mapToGlobal(event.pos())
                except Exception:
                    return False

            # Click inside our window → pass through
            if self.frameGeometry().contains(gp):
                return False

            widget_at = QtWidgets.QApplication.widgetAt(gp)
            if widget_at and (widget_at is self or self.isAncestorOf(widget_at)):
                return False

            # Click outside → hide
            self.hide()
            return False

        return False

    # ------------------------------------------------------------------
    # Right-click button actions
    # ------------------------------------------------------------------
    def _toggle_default_material(self):
        """Right-click +Shelf: toggle Use Default Material on the active viewport.

        This is a command click just like a shelf/pie command, so it obeys the
        global Close on click setting.  +Shelf's normal left click still opens
        the shelf picker and is deliberately unaffected.
        """
        self._prepare_command_execution(None)
        try:
            panel = cmds.getPanel(withFocus=True)
            if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
                panels = cmds.getPanel(type="modelPanel")
                if not panels:
                    cmds.warning("No model panel found.")
                    return
                panel = panels[0]
            current = cmds.modelEditor(panel, q=True, useDefaultMaterial=True)
            cmds.modelEditor(panel, e=True, useDefaultMaterial=not current)
            state = "ON" if not current else "OFF"
            cmds.inViewMessage(
                amg='<span style="color:#F0A500;">Use Default Material:</span> <b>{}</b>'.format(state),
                pos="botCenter", fade=True, fst=500, fad=200
            )
        except Exception as e:
            cmds.warning("ModPanel: toggle default material error: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    def _toggle_workspace(self):
        """Right-click Settings: cycle between the configured workspaces.

        The right-click command obeys Close on click.  Settings' normal left
        click still opens the Settings window and is deliberately unaffected.
        """
        self._prepare_command_execution(None)
        try:
            ws_a, ws_b = self.workspace_cycle[0], self.workspace_cycle[1]
            current = cmds.workspaceLayoutManager(q=True, current=True)
            # If we're on ws_a switch to ws_b, otherwise switch to ws_a.
            target = ws_b if current == ws_a else ws_a
            cmds.workspaceLayoutManager(setCurrent=target)
            cmds.inViewMessage(
                amg="<hl>{}</hl> Workspace".format(target),
                pos="topCenter", fade=True
            )
        except Exception as e:
            cmds.warning("ModPanel: toggle workspace error: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    # ------------------------------------------------------------------
    # Title middle-click action
    # ------------------------------------------------------------------
    def _run_title_click_code(self):
        """Execute the user-defined PhoenixPanel-title middle-click code."""
        code = (self.title_click_code or "").strip()
        if not code:
            return
        code_type = (self.title_click_type or "python").lower()
        self._prepare_command_execution(None)
        try:
            if code_type == "python":
                import __main__
                exec(code, __main__.__dict__)
            else:
                mel.eval(code)
        except Exception as e:
            cmds.warning("ModPanel title click error: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    def _run_title_right_click_code(self):
        """Run the title right-click command, or its default panel-cycle action.

        Both paths obey the global Close on click setting.
        """
        code = (getattr(self, "title_right_click_code", "") or "").strip()
        src = (getattr(self, "title_right_click_type", "python") or "python").lower()
        self._prepare_command_execution(None)
        try:
            if not code:
                self._cycle_tab()
            elif src == "python":
                import __main__
                exec(code, __main__.__dict__)
            else:
                mel.eval(code)
        except Exception as e:
            cmds.warning("ModPanel title right-click: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    def _run_title_double_click_code(self):
        """Run title double-click code or the built-in hot reload.

        With Close on click ON, the built-in reload refreshes the modules but
        leaves the panel closed. With it OFF, reload keeps the historical
        behaviour and reopens the freshly reloaded panel.
        """
        code = (getattr(self, "title_double_click_code", "") or "").strip()
        if not code:
            should_close = self._effective_close_on_click(None)
            if should_close:
                self._ignore_close = True
                self.hide()
            self._reload_phoenix_panel(reopen=not should_close)
            return

        src = (getattr(self, "title_double_click_type", "python") or "python").lower()
        self._prepare_command_execution(None)
        try:
            if src == "python":
                import __main__
                exec(code, __main__.__dict__)
            else:
                mel.eval(code)
        except Exception as e:
            cmds.warning("ModPanel title double-click: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    # ------------------------------------------------------------------
    # Tab cycling (right-click on title)
    # ------------------------------------------------------------------
    def _cycle_tab(self):
        """Advance to next MAIN tab only (0→1→2→0). Hidden panels excluded."""
        next_tab = (self.current_tab % NUM_TABS + 1) % NUM_TABS
        self.switch_tab(next_tab)

    # ------------------------------------------------------------------
    # Look/theme helpers
    # ------------------------------------------------------------------
    def normalize_look_settings(self, raw=None):
        return normalize_look(raw)

    def export_look_settings(self):
        look = normalize_look(getattr(self, "look_theme", None))
        # Keep the three legacy/canonical properties mirrored into the Look
        # payload so standalone Look exports are self-contained.
        look["title_text"] = (getattr(self, "panel_title", "ModPanel")
                              or "ModPanel")
        look["visual_scale"] = max(0.1, min(10.0, float(
            getattr(self, "panel_scale", 1.0))))
        look["button_spacing"] = max(0, min(50, int(
            getattr(self, "padding", 8))))
        return look

    def apply_look_settings(self, raw, save=True, refresh=True):
        """Apply a validated Look payload to the real panel.

        The Settings dialog keeps its own draft and only calls this method
        when the user presses Apply/Save, which guarantees preview edits do
        not leak onto the live panel.
        """
        look = normalize_look(raw)
        self.look_theme = look
        self.panel_title = look["title_text"]
        self.panel_scale = look["visual_scale"]
        self.padding = look["button_spacing"]

        if getattr(self, "_ui_built", False) and refresh:
            self._apply_panel_scale()
            self._apply_look_theme()
            self._grid_dirty = True
            self.rebuild_grid()
            self._grid_dirty = False
            self.update_quick_buttons()
            self._update_title_tab_hint()
            self._update_recent_row()
            if self.isVisible():
                self._resize_to_content()
        if save:
            self.save_global_state()

    def apply_ui_style(self, name, base_look=None, save=True):
        """Switch the whole UI between style presets (ModPanel / Classic)
        instantly: every live widget is re-translated, and the Look colours
        and shape are replaced by the style's preset. Title, scale and
        spacing from ``base_look`` (or the current Look) are preserved."""
        name = _theme.set_style(name)
        look = normalize_look(base_look if isinstance(base_look, dict)
                              else self.export_look_settings())
        look.update(_theme.look_preset(name))
        _theme.restyle_all()
        try:
            from . import utils as _utils
            _utils._ICON_CACHE.pop("__fallback__", None)
        except Exception:
            pass
        self.apply_look_settings(look, save=save, refresh=True)
        self._refresh_pin_icon()
        self.update()
        return name

    def _apply_look_theme(self):
        """Restyle all already-created panel chrome from ``look_theme``."""
        if not getattr(self, "_ui_built", False):
            return
        look = self.export_look_settings()
        self.look_theme = normalize_look(look)
        ps = self.panel_scale
        radius = look["corner_radius"]
        border = look["border_thickness"]
        small_radius = max(0, min(12, int(radius * 0.45)))
        bg_css = _rgba_css(look["panel_background"], look["opacity"])

        if hasattr(self, "bg"):
            _theme.set_qss_look(self.bg, """
            #PanelBg {{
                background-color: {bg};
                border-radius: {radius}px;
                border: {border}px solid {panel_border};
            }}
            """.format(bg=bg_css, radius=radius, border=border,
                       panel_border=look["panel_border"]))

        if hasattr(self, "title_bar_frame"):
            _theme.set_qss_look(self.title_bar_frame, """
            QFrame#TitleBarFrame {{
                background: {title_bar};
                border: none;
                border-radius: {radius}px;
            }}
            """.format(title_bar=look["title_bar"], radius=small_radius))
            lay = self.title_bar_frame.layout()
            if lay is not None:
                lay.setContentsMargins(int(4 * ps), int(2 * ps),
                                       int(4 * ps), int(2 * ps))
                lay.setSpacing(max(1, int(4 * ps)))

        if hasattr(self, "_title_label"):
            _theme.set_qss(self._title_label, "color:{text}; font-weight:bold; font-size:{size}px;".format(
                    text=look["text"], size=max(8, int(12 * ps))))

        common = dict(look)
        common.update(radius=small_radius, border=border,
                      pad=max(0, int(look["button_padding"] * 0.45)),
                      fs=max(8, int(11 * ps)))
        button_qss = """
        QPushButton {{
            background:{button}; color:{icon};
            border:{border}px solid {panel_border};
            border-radius:{radius}px; padding:{pad}px {pad}px;
            font-size:{fs}px;
        }}
        QPushButton:hover {{ background:{button_hover}; border-color:{accent}; }}
        QPushButton:pressed {{ background:{button_pressed}; }}
        QPushButton:checked {{ background:{button_selected}; color:{accent};
                              border-color:{accent}; }}
        """.format(**common)

        for name in ("add_btn", "settings_btn", "_pin_btn"):
            widget = getattr(self, name, None)
            if widget is not None:
                _theme.set_qss_look(widget, button_qss)

        for btn in getattr(self, "quick_buttons", []):
            btn._normal_style()

        if hasattr(self, "_search_bar"):
            _theme.set_qss_look(self._search_bar, """
            QLineEdit {{
                background:{pressed}; color:{text};
                border:{border}px solid {panel_border};
                border-radius:{radius}px; padding:0 8px; font-size:11px;
            }}
            QLineEdit:focus {{ border-color:{accent}; }}
            """.format(pressed=look["button_pressed"], text=look["text"],
                       border=border, panel_border=look["panel_border"],
                       radius=small_radius, accent=look["accent"]))

        if hasattr(self, "_recent_frame"):
            _theme.set_qss_look(self._recent_frame, """
            QFrame#RecentFrame {{ background:{title}; border-radius:{radius}px; }}
            """.format(title=look["title_bar"], radius=small_radius))

        for btn in getattr(self, "button_widgets", []):
            try:
                btn.set_theme(look)
            except Exception:
                pass

        self._update_tab_indicators()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build_ui(self):
        ps = self.panel_scale
        hbs = self.hot_button_icon_scale   # additional scale for the 10 hot buttons + their row height
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.bg = QtWidgets.QWidget()
        self.bg.setObjectName("PanelBg")
        _theme.set_qss(self.bg, """
        #PanelBg {
            background-color: #151820;
            border-radius: 12px;
            border: 1px solid #303645;
        }
        """)
        outer.addWidget(self.bg)

        main = QtWidgets.QVBoxLayout(self.bg)
        main.setContentsMargins(int(10 * ps), int(10 * ps), int(10 * ps), int(10 * ps))
        main.setSpacing(int(8 * ps))
        self._main_layout = main

        # ---- Title row ----
        self.title_bar_frame = QtWidgets.QFrame()
        self.title_bar_frame.setObjectName("TitleBarFrame")
        title_row = QtWidgets.QHBoxLayout(self.title_bar_frame)
        title_row.setContentsMargins(int(4 * ps), int(2 * ps), int(4 * ps), int(2 * ps))
        title_row.setSpacing(int(4 * ps))

        self._title_label = QtWidgets.QLabel(self.panel_title)
        _theme.set_qss(self._title_label, "color: #f5f7ff; font-weight: bold; font-size: {}px;".format(int(12 * ps)))
        self._title_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        # Non-empty placeholder so there's never a window where this has no
        # tooltip at all — _rebuild_title_tooltip() (below) immediately
        # replaces it with the real, up-to-date one.
        self._title_label.setToolTip("Right-click: Switch panel\nDouble-click: Reload ModPanel")
        self._title_label.installEventFilter(self)
        title_row.addWidget(self._title_label)
        self._rebuild_title_tooltip()

        # Quick buttons frame
        self.quick_buttons_frame = QtWidgets.QFrame()
        self.quick_buttons_frame.setObjectName("QuickButtonsFrame")
        self.quick_buttons_frame.setFixedHeight(int(26 * ps * hbs))
        _theme.set_qss(self.quick_buttons_frame, """
        #QuickButtonsFrame {
            border-radius: 4px;
            padding: 2px;
            background-color: transparent;
        }
        """)
        self.quick_buttons_layout = QtWidgets.QHBoxLayout(self.quick_buttons_frame)
        self.quick_buttons_layout.setContentsMargins(int(4 * ps), 0, int(4 * ps), 0)
        self.quick_buttons_layout.setSpacing(int(self.quick_button_gap * ps))
        self.quick_buttons_layout.setAlignment(QtCore.Qt.AlignTop)

        self.quick_buttons = []
        for i in range(NUM_QUICK_BTNS):
            data = self.custom_buttons[i] if i < len(self.custom_buttons) else {}
            btn  = _QuickToolButton(parent=self.quick_buttons_frame)
            btn.setFixedSize(int(24 * ps * hbs), int(24 * ps * hbs))
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
            btn.setIconSize(QtCore.QSize(int(16 * ps * hbs), int(16 * ps * hbs)))
            btn.setToolTip(data.get("tooltip") or data.get("name") or "Button {}".format(i + 1))
            btn._normal_style()
            icon_name = data.get("icon", "")
            if icon_name or data.get("icon_candidates"):
                btn.setIcon(self._resolve_info_icon(data, int(16 * ps * hbs)))
            btn.setVisible(bool(data.get("visible", False)))
            btn.pie_provider = (
                lambda idx=i: self.custom_buttons[idx].get("pie_commands", [])
                if idx < len(self.custom_buttons) else []
            )
            btn.angle_provider = (
                lambda idx=i: self.custom_buttons[idx].get("pie_start_angle")
                if idx < len(self.custom_buttons) else None
            )
            btn.icon_resolver = self._resolve_pie_icon
            btn.clicked.connect(lambda checked=False, idx=i: self._on_quick_button(idx))
            btn.leftClickTriggered.connect(lambda idx=i: self._on_quick_button(idx))
            # Right-click is handled by _QuickToolButton's own mousePressEvent
            # override (see class def above), not the shared eventFilter —
            # that chain wasn't reliably delivering right-clicks for these
            # buttons, so this bypasses it entirely and fires straight off
            # the widget's own event handling, the same path left-click
            # already uses successfully.
            btn.rightClicked.connect(
                lambda pos, idx=i, b=btn: self._on_quick_button_rc(idx, b, pos)
            )
            btn.pieCommandTriggered.connect(
                lambda cmd, idx=i: self._on_hotbutton_pie_selected(idx, cmd)
            )
            self.quick_buttons.append(btn)

        title_row.addWidget(self.quick_buttons_frame, 1)

        # +Shelf button
        self.add_btn = QtWidgets.QPushButton("+ Shelf")
        self.add_btn.setFixedHeight(int(24 * ps))
        _theme.set_qss(self.add_btn, """
        QPushButton {{
            background: #252a39;
            color: #c8d2ff;
            border-radius: 6px;
            padding: {padv}px {padh}px;
            font-size: {fs}px;
        }}
        QPushButton:hover {{ background: #2f3547; }}
        """.format(padv=int(2 * ps), padh=int(8 * ps), fs=int(11 * ps)))
        self.add_btn.setToolTip("Left: Add shelf buttons  |  Right-click: Toggle default material")
        self.add_btn.installEventFilter(self)
        title_row.addWidget(self.add_btn)

        # Settings button
        self.settings_btn = QtWidgets.QPushButton("\u2699")
        self.settings_btn.setFixedSize(int(26 * ps), int(26 * ps))
        _theme.set_qss(self.settings_btn, """
            QPushButton {{
                background: #252a39;
                color: #c8d2ff;
                border-radius: 6px;
                font-size: {fs}px;
            }}
            QPushButton:hover {{ background: #32384c; }}
        """.format(fs=int(14 * ps)))
        self.settings_btn.setToolTip("Left: Settings  |  Right-click: Toggle workspace (configurable in Settings)")
        self.settings_btn.installEventFilter(self)
        title_row.addWidget(self.settings_btn)

        # Pin button — keeps panel open on outside-click. The glyph is
        # painted onto a pixmap ourselves (see _render_glyph_icon / 
        # _refresh_pin_icon) rather than set as button text — QPushButton
        # centers TEXT using the font's advance-width box, which doesn't
        # match this glyph's visual bounds, and no fixed-pixel padding
        # correction stays right once the button's size changes with
        # panel_scale. An icon we've already centered ourselves sidesteps
        # that entirely.
        self._pin_btn = QtWidgets.QPushButton("")
        self._pin_btn.setFixedSize(int(26 * ps), int(26 * ps))
        self._pin_btn.setCheckable(True)
        self._pin_btn.setToolTip("Pin panel — stays open on outside click  (X to search)")
        _theme.set_qss(self._pin_btn, """
            QPushButton {
                background: #252a39; border: none; border-radius: 6px;
            }
            QPushButton:hover    { background: #32384c; }
            QPushButton:checked  { background: #2a3a5a; }
        """)
        self._pin_btn.toggled.connect(lambda _checked=False: self._refresh_pin_icon())
        self._pin_btn.clicked.connect(self._toggle_pin)
        title_row.addWidget(self._pin_btn)
        self._refresh_pin_icon()

        main.addWidget(self.title_bar_frame)

        # ---- Tab indicator bar (3 thin segments, always visible) ----
        tab_bar = QtWidgets.QHBoxLayout()
        tab_bar.setSpacing(3)
        tab_bar.setContentsMargins(0, 0, 0, 0)

        self._tab_indicators = []
        _NAMES = ["General", "UV Editing", "Hypershade"]
        for i in range(NUM_TABS):
            seg = QtWidgets.QFrame()
            seg.setFixedHeight(3)
            seg.setToolTip(_NAMES[i])
            # Click on a segment also switches directly
            seg.mousePressEvent = lambda _evt, idx=i: self.switch_tab(idx)
            seg.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            tab_bar.addWidget(seg, 1)
            self._tab_indicators.append(seg)

        main.addLayout(tab_bar)
        self._update_tab_indicators()

        # ---- Search bar (hidden unless search_always_on or user presses X) ----
        self._search_bar = QtWidgets.QLineEdit()
        self._search_bar.setPlaceholderText("  🔍  Search buttons…")
        self._search_bar.setFixedHeight(26)
        _theme.set_qss(self._search_bar, """
        QLineEdit {
            background: #10131a; color: #c8d2ff;
            border: 1px solid #2a3050; border-radius: 5px;
            padding: 0 8px; font-size: 11px;
        }
        QLineEdit:focus { border-color: #4a7bb8; }
        """)
        self._search_bar.setVisible(self.search_always_on)
        self._search_bar.textChanged.connect(self._apply_search_filter)
        self._search_bar.installEventFilter(self)
        main.addWidget(self._search_bar)

        # ---- Recent commands strip ----
        self._recent_frame = QtWidgets.QFrame()
        self._recent_frame.setObjectName("RecentFrame")
        self._recent_frame.setFixedHeight(30)
        _theme.set_qss(self._recent_frame, """
        QFrame#RecentFrame {
            background: #111420; border-radius: 5px;
        }
        """)
        self._recent_layout = QtWidgets.QHBoxLayout(self._recent_frame)
        self._recent_layout.setContentsMargins(6, 4, 6, 4)
        self._recent_layout.setSpacing(4)
        self._recent_frame.setVisible(False)  # shown after _update_recent_row
        main.addWidget(self._recent_frame)
        self.scroll_wrapper = QtWidgets.QWidget()
        self.scroll_wrapper.setObjectName("ScrollWrapper")
        _theme.set_qss(self.scroll_wrapper, """
        #ScrollWrapper {
            background-color: #373737;
            border-radius: 10px;
        }
        """)
        scroll_wrapper_layout = QtWidgets.QVBoxLayout(self.scroll_wrapper)
        scroll_wrapper_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        _theme.set_qss(self.scroll, """
        QScrollArea {
            background: transparent;
            border-radius: 10px;
        }
        QScrollArea > QWidget > QWidget {
            background: transparent;
        }
        QScrollBar:vertical {
            background: #373737;
            width: 6px;
            border-radius: 3px;
        }
        QScrollBar::handle:vertical {
            background: #3a4055;
            border-radius: 3px;
            min-height: 20px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            background: #373737;
            height: 6px;
            border-radius: 3px;
        }
        QScrollBar::handle:horizontal {
            background: #3a4055;
            border-radius: 3px;
            min-width: 20px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        """)
        scroll_wrapper_layout.addWidget(self.scroll)
        main.addWidget(self.scroll_wrapper, 1)

        # grid_container uses a VBoxLayout of HBox rows for per-row alignment
        self.grid_container = QtWidgets.QWidget()
        _theme.set_qss(self.grid_container, "background: transparent;")
        self.grid_layout = QtWidgets.QVBoxLayout(self.grid_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(0)
        self.grid_layout.setAlignment(QtCore.Qt.AlignTop)

        self.scroll.setWidget(self.grid_container)

        # Signals
        self.add_btn.clicked.connect(self.open_shelf_picker)
        self.settings_btn.clicked.connect(self.open_settings_window)

        self._rebuild_quick_buttons_layout()
        self._apply_look_theme()

    # ------------------------------------------------------------------
    # Tab indicator styles
    # ------------------------------------------------------------------
    # Colour palette per tab: (active_colour, inactive_colour)
    _TAB_COLOURS = [
        ("#4a7bb8", "#303645"),   # 0 – General  – blue
        ("#3aaa6e", "#303645"),   # 1 – UV       – green
        ("#b86a2a", "#303645"),   # 2 – Hyper    – orange
    ]

    def _update_tab_indicators(self):
        if not hasattr(self, "_tab_indicators"):
            return
        look = self.export_look_settings()
        for i, seg in enumerate(self._tab_indicators):
            colour = look["accent"] if i == self.current_tab else look["panel_border"]
            _theme.set_qss(seg, "QFrame {{ background: {}; border-radius: 1px; }}".format(colour))

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------
    def switch_tab(self, tab_index):
        if tab_index == self.current_tab:
            return
        if tab_index < 0 or tab_index >= _TOTAL_TABS:
            return

        self.save_tab_config(self.current_tab)
        self.current_tab = tab_index
        self.load_tab_config(tab_index)
        self._grid_dirty = True

        if self._ui_built:
            self._apply_panel_scale()
            self._apply_look_theme()
            self.rebuild_grid()
            self.update_quick_buttons()
            self._update_tab_indicators()
            self._update_title_tab_hint(); self._rebuild_title_tooltip()

        self.save_global_state()

    def _update_title_tab_hint(self):
        """Update title bar: plain name for main tabs, key hint for hidden panels."""
        if not hasattr(self, "_title_label"):
            return
        if getattr(self, "_free_stuff_active", False):
            self._title_label.setText("{}  \u00b7  Free Stuff".format(self.panel_title))
            return
        if self.current_tab >= NUM_TABS:
            hidden_idx = self.current_tab - NUM_TABS
            if hidden_idx < len(self._HIDDEN_TAB_LABELS):
                hint = self._HIDDEN_TAB_LABELS[hidden_idx]
            else:
                hint = str(hidden_idx + 1)
            self._title_label.setText("{}  \u00b7  {}".format(self.panel_title, hint))
        else:
            self._title_label.setText(self.panel_title)

    def _rebuild_title_tooltip(self):
        """Compose the title's tooltip from whichever interactions actually
        have something configured. Right-click and double-click always
        have SOME behaviour (a custom command, or their sensible default —
        switch panel / reload), so they always contribute a line; middle
        click has no default action at all, so it's only mentioned when a
        command has actually been assigned. This also fixes a real bug:
        previously the tooltip was a single string set once at construction
        and never revisited, so if every optional piece happened to be
        blank the whole tooltip could end up empty."""
        if not hasattr(self, "_title_label"):
            return
        lines = []

        mc_code = (getattr(self, "title_click_code", "") or "").strip()
        if mc_code:
            mc_tip = (getattr(self, "title_click_tooltip", "") or "").strip()
            lines.append("Middle-click: {}".format(mc_tip or "Run custom command"))

        rc_code = (getattr(self, "title_right_click_code", "") or "").strip()
        rc_tip  = (getattr(self, "title_right_click_tooltip", "") or "").strip()
        lines.append("Right-click: {}".format(
            rc_tip or ("Run custom command" if rc_code else "Switch panel")))

        dc_code = (getattr(self, "title_double_click_code", "") or "").strip()
        dc_tip  = (getattr(self, "title_double_click_tooltip", "") or "").strip()
        lines.append("Double-click: {}".format(
            dc_tip or ("Run custom command" if dc_code else "Reload ModPanel")))

        if not lines:
            lines = ["Right-click: Switch panel", "Double-click: Reload ModPanel"]

        self._title_label.setToolTip("\n".join(lines))

    # ------------------------------------------------------------------
    # Config paths
    # ------------------------------------------------------------------
    def get_tab_config_path(self, tab_index):
        return "{}_tab{}.json".format(self.config_base_path, tab_index)

    def get_global_config_path(self):
        return "{}_global.json".format(self.config_base_path)

    # ------------------------------------------------------------------
    # Global state (last used tab)
    # ------------------------------------------------------------------
    def load_global_state(self):
        path = self.get_global_config_path()
        if not os.path.exists(path):
            self.current_tab = 0
            _theme.set_style(_theme.DEFAULT_STYLE)
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.look_theme = normalize_look(data.get("look"))
            self.current_tab = int(data.get("last_tab", 0))
            # Clamp to main tabs only — hidden panels don't persist as start tab
            if not (0 <= self.current_tab < NUM_TABS):
                self.current_tab = 0
            # Load shared right-click actions
            rc_list = data.get("quick_button_rc", [])
            for i in range(NUM_QUICK_BTNS):
                if i < len(rc_list) and isinstance(rc_list[i], dict):
                    self.quick_button_rc[i] = {
                        "name": rc_list[i].get("name", ""),
                        "code": rc_list[i].get("code", ""),
                        "type": rc_list[i].get("type", "python"),
                        "icon": rc_list[i].get("icon", ""),
                    }
            # Load workspace cycle pair
            wc = data.get("workspace_cycle")
            if isinstance(wc, list) and len(wc) == 2 and all(isinstance(s, str) for s in wc):
                self.workspace_cycle = wc
            # Load UV tab workspace trigger
            uv_ws = data.get("uv_tab_workspace", "").strip()
            if uv_ws:
                self.uv_tab_workspace = uv_ws
            self.tab_workspaces = {"uv": self.uv_tab_workspace,
                                   "node_detect": self.node_detection_enabled}
            # Load shared hot buttons. New configs store one authoritative
            # count; older configs are migrated from their sequential visible flags.
            self._load_custom_buttons(data.get("quick_buttons", []))
            if "quick_button_count" in data:
                self.quick_button_count = self._clamp_quick_button_count(
                    data.get("quick_button_count", 0)
                )
            else:
                self.quick_button_count = self._derive_quick_button_count()
            self._apply_quick_button_count()
            # Load shared layout settings
            self.cols                    = int(data.get("cols",                    self.cols))
            self.button_scale            = float(data.get("button_scale",          self.button_scale))
            self.panel_scale             = max(0.1, min(10.0, float(
                                              data.get("panel_scale",
                                                       self.look_theme["visual_scale"]))))
            self.padding                 = int(data.get("padding",
                                                       self.look_theme["button_spacing"]))
            self.quick_alignment         = int(data.get("quick_alignment",         self.quick_alignment))
            self.grid_full_row_alignment = int(data.get("grid_full_row_alignment", self.grid_full_row_alignment))
            self.grid_row_alignment      = int(data.get("grid_row_alignment",      self.grid_row_alignment))
            self.close_on_click          = bool(data.get("close_on_click",          True))
            self.search_always_on        = bool(data.get("search_always_on",        False))
            self.recent_commands_enabled = bool(data.get("recent_commands_enabled", True))
            self.node_detection_enabled  = bool(data.get("node_detection_enabled",  True))
            self.quick_button_gap        = int(data.get("quick_button_gap",         4))
            self.pie_icon_scale          = max(0.5, min(1.5, float(
                                              data.get("pie_icon_scale", 1.0))))
            self.hot_pie_icon_scale      = max(0.5, min(1.5, float(
                                              data.get("hot_pie_icon_scale", 1.0))))
            self.hot_button_icon_scale   = max(0.5, min(3.0, float(
                                              data.get("hot_button_icon_scale", 1.0))))
            self.pie_hold_delay_ms       = max(0, min(2000, int(
                                              data.get("pie_hold_delay_ms", 100))))
            self.pie_dim_enabled         = bool(data.get("pie_dim_enabled", True))
            self.pie_dim_mode            = (data.get("pie_dim_mode", "panel") or "panel").lower()
            if self.pie_dim_mode not in ("panel", "screen"):
                self.pie_dim_mode = "panel"
            self.pie_dim_delay_ms        = max(0, min(2000, int(
                                              data.get("pie_dim_delay_ms", 150))))
            self.pie_dim_fade_ms         = max(0, min(2000, int(
                                              data.get("pie_dim_fade_ms", 200))))
            self.pie_dim_opacity         = max(10, min(100, int(
                                              data.get("pie_dim_opacity", 55))))
            self.pie_start_angle         = max(-360.0, min(360.0, float(
                                              data.get("pie_start_angle", -90.0))))
            self.panel_title             = (data.get("panel_title",
                                                     self.look_theme["title_text"])
                                            or "ModPanel")
            # Keep mirrored fields canonical even when an old configuration has
            # no Look payload or when top-level legacy values take precedence.
            self.look_theme["title_text"] = self.panel_title
            self.look_theme["visual_scale"] = self.panel_scale
            self.look_theme["button_spacing"] = self.padding
            # UI style. Configs saved before ModPanel have no "ui_style": move
            # them to the ModPanel default. Look values still at their classic
            # defaults (and the old default title) are converted; values the
            # user customised are kept as they are.
            if "ui_style" in data:
                _theme.set_style(data.get("ui_style"))
            else:
                _theme.set_style(_theme.DEFAULT_STYLE)
                self.look_theme = _theme.migrate_classic_look(self.look_theme)
                if self.panel_title == "PhoenixPanel":
                    self.panel_title = "ModPanel"
                    self.look_theme["title_text"] = self.panel_title
            rc_raw = data.get("recent_commands", [])
            self.recent_commands = rc_raw if isinstance(rc_raw, list) else []
        except Exception:
            self.current_tab = 0

    def save_global_state(self):
        path = self.get_global_config_path()
        try:
            with open(path, "w") as f:
                json.dump({
                    "last_tab":              self.current_tab if self.current_tab < NUM_TABS else 0,
                    "quick_button_rc":       self.quick_button_rc,
                    "quick_buttons":         self.custom_buttons,
                    "workspace_cycle":       self.workspace_cycle,
                    "uv_tab_workspace":      self.uv_tab_workspace,
                    "cols":                  self.cols,
                    "button_scale":          self.button_scale,
                    "panel_scale":           self.panel_scale,
                    "padding":               self.padding,
                    "quick_alignment":       self.quick_alignment,
                    "grid_full_row_alignment": self.grid_full_row_alignment,
                    "grid_row_alignment":    self.grid_row_alignment,
                    "close_on_click":        self.close_on_click,
                    "search_always_on":      self.search_always_on,
                    "recent_commands_enabled": self.recent_commands_enabled,
                    "node_detection_enabled":  self.node_detection_enabled,
                    "quick_button_gap":      self.quick_button_gap,
                    "quick_button_count":    self.quick_button_count,
                    "pie_icon_scale":        self.pie_icon_scale,
                    "hot_pie_icon_scale":    self.hot_pie_icon_scale,
                    "hot_button_icon_scale": self.hot_button_icon_scale,
                    "pie_hold_delay_ms":     self.pie_hold_delay_ms,
                    "pie_dim_enabled":       self.pie_dim_enabled,
                    "pie_dim_mode":          self.pie_dim_mode,
                    "pie_dim_delay_ms":      self.pie_dim_delay_ms,
                    "pie_dim_fade_ms":       self.pie_dim_fade_ms,
                    "pie_dim_opacity":       self.pie_dim_opacity,
                    "pie_start_angle":       self.pie_start_angle,
                    "panel_title":           self.panel_title,
                    "look":                  self.export_look_settings(),
                    "ui_style":              _theme.current_style(),
                    "recent_commands":       self.recent_commands[:16],
                }, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Per-tab config  load / save
    # ------------------------------------------------------------------
    def load_tab_config(self, tab_index):
        self._reset_tab_state()
        path = self.get_tab_config_path(tab_index)
        if not os.path.exists(path):
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception:
            return

        panel = data.get("panel", {})
        self.title_click_code       = panel.get("title_click_code",       "")
        self.title_click_type       = panel.get("title_click_type",       "python")
        self.title_right_click_code = panel.get("title_right_click_code", "")
        self.title_right_click_type = panel.get("title_right_click_type", "python")
        self.title_double_click_code = panel.get("title_double_click_code", "")
        self.title_double_click_type = panel.get("title_double_click_type", "python")
        self.title_click_tooltip          = panel.get("title_click_tooltip", "")
        self.title_right_click_tooltip    = panel.get("title_right_click_tooltip", "")
        self.title_double_click_tooltip   = panel.get("title_double_click_tooltip", "")

        self.buttons_data = data.get("buttons", []) or []
        for _info in self.buttons_data:
            if isinstance(_info, dict):
                _info["pie_commands"] = _sanitize_pie_commands(_info.get("pie_commands", []))

    def save_tab_config(self, tab_index):
        if getattr(self, "_free_stuff_active", False):
            # buttons_data currently holds the transient Free Stuff catalog,
            # not this tab's real buttons — never let that hit disk.
            return
        path = self.get_tab_config_path(tab_index)
        data = {
            "panel": {
                "title_click_code":       self.title_click_code,
                "title_click_type":       self.title_click_type,
                "title_right_click_code": self.title_right_click_code,
                "title_right_click_type": self.title_right_click_type,
                "title_double_click_code": getattr(self, "title_double_click_code", ""),
                "title_double_click_type": getattr(self, "title_double_click_type", "python"),
                "title_click_tooltip":        getattr(self, "title_click_tooltip", ""),
                "title_right_click_tooltip":  getattr(self, "title_right_click_tooltip", ""),
                "title_double_click_tooltip": getattr(self, "title_double_click_tooltip", ""),
            },
            "buttons": self.buttons_data,
        }
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # Alias used by settings dialog
    def save_config(self):
        self.save_tab_config(self.current_tab)

    def reset_all(self):
        """Factory reset — clears every panel, every hot button, and all title click codes."""
        # Reset shared hot buttons and right-click actions
        self.custom_buttons = [
            {"name": "BTN{}".format(i + 1), "tooltip": "",
             "type": "mel", "code": "", "icon": "", "visible": False,
             "invert_close_on_click": False, "pie_commands": []}
            for i in range(NUM_QUICK_BTNS)
        ]
        self.quick_button_rc = [
            {"name": "", "code": "", "type": "python", "icon": ""}
            for _ in range(NUM_QUICK_BTNS)
        ]
        self.quick_button_count = 0
        self.look_theme = normalize_look()
        self.panel_title = self.look_theme["title_text"]
        self.panel_scale = self.look_theme["visual_scale"]
        self.padding = self.look_theme["button_spacing"]

        # Clear all 7 tab configs
        _empty_panel = {
            "title_click_code":       "",
            "title_click_type":       "python",
            "title_right_click_code": "",
            "title_right_click_type": "python",
            "title_double_click_code": "",
            "title_double_click_type": "python",
            "title_click_tooltip":        "",
            "title_right_click_tooltip":  "",
            "title_double_click_tooltip": "",
        }
        for i in range(_TOTAL_TABS):
            if i == self.current_tab:
                self.buttons_data           = []
                self.title_click_code       = ""
                self.title_click_type       = "python"
                self.title_right_click_code = ""
                self.title_right_click_type = "python"
                self.title_double_click_code = ""
                self.title_double_click_type = "python"
                self.title_click_tooltip          = ""
                self.title_right_click_tooltip    = ""
                self.title_double_click_tooltip   = ""
            else:
                path = self.get_tab_config_path(i)
                try:
                    with open(path, "w") as f:
                        json.dump({"panel": _empty_panel, "buttons": []}, f, indent=2)
                except Exception:
                    pass

        # Refresh UI and persist
        self._grid_dirty = True
        if self._ui_built:
            self._apply_panel_scale()
            self._apply_look_theme()
            self.rebuild_grid()
            self._grid_dirty = False
            self.update_quick_buttons()
            self._update_title_tab_hint()
        self.save_tab_config(self.current_tab)
        self.save_global_state()

    # ------------------------------------------------------------------
    # Hot-button normalization helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clamp_quick_button_count(value):
        try:
            return max(0, min(NUM_QUICK_BTNS, int(value)))
        except (TypeError, ValueError):
            return 0

    def _derive_quick_button_count(self):
        """Migrate old sequential visible flags into the new count model."""
        count = 0
        for data in self.custom_buttons[:NUM_QUICK_BTNS]:
            if not bool(data.get("visible", False)):
                break
            count += 1
        return count

    def _apply_quick_button_count(self):
        """Make legacy per-button visible flags mirror quick_button_count."""
        self.quick_button_count = self._clamp_quick_button_count(
            getattr(self, "quick_button_count", 0)
        )
        for i, data in enumerate(self.custom_buttons[:NUM_QUICK_BTNS]):
            data["visible"] = i < self.quick_button_count

    def set_quick_button_count(self, value, save=False):
        """Set the number of shown hot buttons and refresh the live panel."""
        self.quick_button_count = self._clamp_quick_button_count(value)
        self._apply_quick_button_count()
        if self._ui_built:
            self.update_quick_buttons()
        if save:
            self.save_global_state()

    def _load_custom_buttons(self, raw):
        """Normalise a raw quick_buttons list and assign to self.custom_buttons."""
        if not isinstance(raw, list) or not raw:
            return
        normalized = []
        for i, q in enumerate(raw[:NUM_QUICK_BTNS]):
            if not isinstance(q, dict):
                continue
            normalized.append({
                "name":    (q.get("name") or "BTN{}".format(i + 1))[:6],
                "tooltip": q.get("tooltip", ""),
                "type":    (q.get("type", "mel") or "mel").lower(),
                "code":    q.get("code", ""),
                "icon":    q.get("icon", ""),
                "visible": bool(q.get("visible", False)),
                "invert_close_on_click": bool(q.get("invert_close_on_click", False)),
                "pie_commands": _sanitize_pie_commands(q.get("pie_commands", [])),
                "pie_start_angle": q.get("pie_start_angle", None),
            })
        while len(normalized) < NUM_QUICK_BTNS:
            normalized.append({
                "name": "BTN{}".format(len(normalized) + 1),
                "tooltip": "", "type": "mel", "code": "", "icon": "", "visible": False,
                "invert_close_on_click": False, "pie_commands": [],
            })
        self.custom_buttons = normalized

    # ------------------------------------------------------------------
    # All-panels import / export
    # ------------------------------------------------------------------
    def export_all_tabs(self):
        """Return a JSON-serialisable dict covering every tab's buttons,
        per-tab title click actions, and shared hot buttons.
        Suitable for writing to a preset file (version 6 format — adds the
        complete Look payload while retaining every older top-level key).
        """
        tabs = {}
        for i in range(_TOTAL_TABS):
            if i == self.current_tab:
                tabs[str(i)] = {
                    "buttons":               self.buttons_data,
                    "title_click_code":      self.title_click_code,
                    "title_click_type":      self.title_click_type,
                    "title_right_click_code": self.title_right_click_code,
                    "title_right_click_type": self.title_right_click_type,
                    "title_double_click_code": getattr(self, "title_double_click_code", ""),
                    "title_double_click_type": getattr(self, "title_double_click_type", "python"),
                    "title_click_tooltip":        getattr(self, "title_click_tooltip", ""),
                    "title_right_click_tooltip":  getattr(self, "title_right_click_tooltip", ""),
                    "title_double_click_tooltip": getattr(self, "title_double_click_tooltip", ""),
                }
            else:
                path = self.get_tab_config_path(i)
                try:
                    if os.path.exists(path):
                        with open(path, "r") as f:
                            raw = json.load(f)
                        panel_cfg = raw.get("panel", {})
                        tabs[str(i)] = {
                            "buttons":               raw.get("buttons", []),
                            "title_click_code":      panel_cfg.get("title_click_code", ""),
                            "title_click_type":      panel_cfg.get("title_click_type", "python"),
                            "title_right_click_code": panel_cfg.get("title_right_click_code", ""),
                            "title_right_click_type": panel_cfg.get("title_right_click_type", "python"),
                            "title_double_click_code": panel_cfg.get("title_double_click_code", ""),
                            "title_double_click_type": panel_cfg.get("title_double_click_type", "python"),
                            "title_click_tooltip":        panel_cfg.get("title_click_tooltip", ""),
                            "title_right_click_tooltip":  panel_cfg.get("title_right_click_tooltip", ""),
                            "title_double_click_tooltip": panel_cfg.get("title_double_click_tooltip", ""),
                        }
                    else:
                        tabs[str(i)] = {"buttons": [], "title_click_code": "",
                                        "title_click_type": "python",
                                        "title_right_click_code": "",
                                        "title_right_click_type": "python"}
                except Exception:
                    tabs[str(i)] = {"buttons": [], "title_click_code": "",
                                    "title_click_type": "python",
                                    "title_right_click_code": "",
                                    "title_right_click_type": "python"}
        return {
            "version":           6,
            "tabs":              tabs,
            "quick_buttons":     self.custom_buttons,
            "quick_button_rc":   self.quick_button_rc,
            "quick_button_count": self.quick_button_count,
            "panel_title":       self.panel_title,
            "look":              self.export_look_settings(),
        }

    def import_all_tabs(self, cfg, choices=None):
        """Apply an exported preset dict selectively.

        choices: dict with boolean flags controlling what gets imported:
            "panels"       — panel button layouts for all 7 tabs
            "quick_buttons"— hot button configs, click actions, and shown count
            "title_actions"— per-tab title middle/right-click codes
            "look"         — appearance, title text, visual scale, and spacing
        All default to True when choices is None.
        """
        if choices is None:
            choices = {"panels": True, "quick_buttons": True,
                       "title_actions": True, "look": True}

        import_panels  = choices.get("panels", True)
        import_hotbtns = choices.get("quick_buttons", True)
        import_title   = choices.get("title_actions", True)
        import_look    = choices.get("look", True)

        tabs_data = cfg.get("tabs", {})
        version   = cfg.get("version", 2)

        for tab_str, tab_cfg in tabs_data.items():
            try:
                idx = int(tab_str)
            except (ValueError, TypeError):
                continue
            if not (0 <= idx < _TOTAL_TABS):
                continue

            # v2 compat: tab_cfg may be a plain list of buttons
            if isinstance(tab_cfg, list):
                buttons = tab_cfg
                title_code = title_type = title_rc_code = title_rc_type = None
                title_dc_code = title_dc_type = None
                title_tip = title_rc_tip = title_dc_tip = None
            else:
                buttons        = tab_cfg.get("buttons", [])
                title_code     = tab_cfg.get("title_click_code")
                title_type     = tab_cfg.get("title_click_type")
                title_rc_code  = tab_cfg.get("title_right_click_code")
                title_rc_type  = tab_cfg.get("title_right_click_type")
                title_dc_code  = tab_cfg.get("title_double_click_code")
                title_dc_type  = tab_cfg.get("title_double_click_type")
                title_tip      = tab_cfg.get("title_click_tooltip")
                title_rc_tip   = tab_cfg.get("title_right_click_tooltip")
                title_dc_tip   = tab_cfg.get("title_double_click_tooltip")

            if idx == self.current_tab:
                if import_panels:
                    self.buttons_data = list(buttons or [])
                    for _info in self.buttons_data:
                        if isinstance(_info, dict):
                            _info["pie_commands"] = _sanitize_pie_commands(
                                _info.get("pie_commands", []))
                if import_title:
                    if title_code  is not None: self.title_click_code       = title_code
                    if title_type  is not None: self.title_click_type       = title_type
                    if title_rc_code is not None: self.title_right_click_code = title_rc_code
                    if title_rc_type is not None: self.title_right_click_type = title_rc_type
                    if title_dc_code is not None: self.title_double_click_code = title_dc_code
                    if title_dc_type is not None: self.title_double_click_type = title_dc_type
                    if title_tip     is not None: self.title_click_tooltip = title_tip
                    if title_rc_tip  is not None: self.title_right_click_tooltip = title_rc_tip
                    if title_dc_tip  is not None: self.title_double_click_tooltip = title_dc_tip
            else:
                tab_path = self.get_tab_config_path(idx)
                existing = {}
                try:
                    if os.path.exists(tab_path):
                        with open(tab_path, "r") as f:
                            existing = json.load(f)
                except Exception:
                    pass
                panel_cfg = existing.get("panel", {})
                if import_panels:
                    existing["buttons"] = list(buttons or [])
                if import_title:
                    if title_code    is not None: panel_cfg["title_click_code"]       = title_code
                    if title_type    is not None: panel_cfg["title_click_type"]       = title_type
                    if title_rc_code is not None: panel_cfg["title_right_click_code"] = title_rc_code
                    if title_rc_type is not None: panel_cfg["title_right_click_type"] = title_rc_type
                    if title_dc_code is not None: panel_cfg["title_double_click_code"] = title_dc_code
                    if title_dc_type is not None: panel_cfg["title_double_click_type"] = title_dc_type
                    if title_tip     is not None: panel_cfg["title_click_tooltip"] = title_tip
                    if title_rc_tip  is not None: panel_cfg["title_right_click_tooltip"] = title_rc_tip
                    if title_dc_tip  is not None: panel_cfg["title_double_click_tooltip"] = title_dc_tip
                existing["panel"] = panel_cfg
                try:
                    with open(tab_path, "w") as f:
                        json.dump(existing, f, indent=2)
                except Exception:
                    pass

        if import_hotbtns:
            self._load_custom_buttons(cfg.get("quick_buttons", []))
            rc_list = cfg.get("quick_button_rc", [])
            if isinstance(rc_list, list):
                for i in range(min(NUM_QUICK_BTNS, len(rc_list))):
                    if isinstance(rc_list[i], dict):
                        self.quick_button_rc[i] = {
                            "name": rc_list[i].get("name", ""),
                            "code": rc_list[i].get("code", ""),
                            "type": rc_list[i].get("type", "python"),
                            "icon": rc_list[i].get("icon", ""),
                        }
            if "quick_button_count" in cfg:
                self.quick_button_count = self._clamp_quick_button_count(
                    cfg.get("quick_button_count", 0)
                )
            else:
                self.quick_button_count = self._derive_quick_button_count()
            self._apply_quick_button_count()

        if import_look and isinstance(cfg.get("look"), dict):
            # Defer UI refresh until the rest of the preset has been applied.
            self.apply_look_settings(cfg.get("look"), save=False, refresh=False)

        # Backward-compatible: older presets simply won't have this key.
        # Keep the historic top-level title authoritative when present.
        if "panel_title" in cfg and (import_look or not isinstance(cfg.get("look"), dict)):
            self.panel_title = cfg.get("panel_title") or "ModPanel"
            self.look_theme["title_text"] = self.panel_title

        self._grid_dirty = True
        if self._ui_built:
            self._apply_panel_scale()
            self._apply_look_theme()
            self.rebuild_grid()
            self._grid_dirty = False
            self.update_quick_buttons()
            self._update_title_tab_hint()
            self._rebuild_title_tooltip()
        self.save_tab_config(self.current_tab)
        self.save_global_state()

    # ------------------------------------------------------------------
    # Workspace-aware auto tab-switch (lightweight polling)
    # ------------------------------------------------------------------
    def _start_workspace_polling(self):
        pass  # Polling removed — tab detection happens on open only (much faster)

    def _poll_workspace(self):
        pass

    def _stop_workspace_polling(self):
        if self._workspace_poll_timer is not None:
            try:
                self._workspace_poll_timer.stop()
            except Exception:
                pass
            self._workspace_poll_timer = None

    # ------------------------------------------------------------------
    # Quick buttons helpers
    # ------------------------------------------------------------------
    def _rebuild_quick_buttons_layout(self):
        while self.quick_buttons_layout.count():
            self.quick_buttons_layout.takeAt(0)

        visible_buttons = [
            btn for i, btn in enumerate(self.quick_buttons)
            if i < self._clamp_quick_button_count(
                getattr(self, "quick_button_count", 0))
        ]

        if self.quick_alignment == 0:   # LEFT
            for b in visible_buttons:
                self.quick_buttons_layout.addWidget(b)
            self.quick_buttons_layout.addStretch(1)
        elif self.quick_alignment == 1: # CENTER
            self.quick_buttons_layout.addStretch(1)
            for b in visible_buttons:
                self.quick_buttons_layout.addWidget(b)
            self.quick_buttons_layout.addStretch(1)
        else:                           # RIGHT
            self.quick_buttons_layout.addStretch(1)
            for b in visible_buttons:
                self.quick_buttons_layout.addWidget(b)

    def update_quick_buttons(self):
        if not self.quick_buttons:
            return
        while len(self.custom_buttons) < NUM_QUICK_BTNS:
            self.custom_buttons.append({
                "name": "BTN{}".format(len(self.custom_buttons) + 1),
                "tooltip": "", "type": "mel", "code": "", "icon": "", "visible": False,
                "invert_close_on_click": False, "pie_commands": [],
            })
        while len(self.quick_button_rc) < NUM_QUICK_BTNS:
            self.quick_button_rc.append(
                {"name": "", "code": "", "type": "python", "icon": ""}
            )

        # One slider-controlled count is authoritative. Visible flags remain in
        # saved button records only for backward compatibility with old presets.
        self._apply_quick_button_count()

        # Sync spacing/size in case quick_button_gap, panel_scale, or
        # hot_button_icon_scale changed via settings since these buttons
        # were first created.
        ps = self.panel_scale
        hbs = self.hot_button_icon_scale
        if hasattr(self, "quick_buttons_layout"):
            self.quick_buttons_layout.setSpacing(int(self.quick_button_gap * ps))
        hot_side = int(24 * ps * hbs)
        hot_icon = int(16 * ps * hbs)
        for _btn in self.quick_buttons:
            if _btn.width() != hot_side or _btn.height() != hot_side:
                _btn.setFixedSize(hot_side, hot_side)
            if _btn.iconSize().width() != hot_icon:
                _btn.setIconSize(QtCore.QSize(hot_icon, hot_icon))

        for i, btn in enumerate(self.quick_buttons):
            data       = self.custom_buttons[i]
            visible     = i < self.quick_button_count
            rc          = self.quick_button_rc[i] if i < len(self.quick_button_rc) else {}
            lc_has_code = bool((data.get("code") or "").strip())
            rc_has_code = bool((rc.get("code") or "").strip())

            icon_name = data.get("icon", "")
            if icon_name or data.get("icon_candidates"):
                btn.setIcon(self._resolve_info_icon(data, hot_icon))
            else:
                btn.setIcon(QtGui.QIcon())

            # Rich-text tooltip: exact, unclamped text, no surrounding quotes,
            # each line carrying its OWN icon inline — LC uses the button's
            # main icon, RC uses whatever icon was captured for the
            # right-click action (they are independent).
            def _icon_html_for(_icon_name):
                if not _icon_name:
                    return ""
                try:
                    from .utils import icon_data_uri as _icon_uri
                    _uri = _icon_uri(_icon_name, size=14)
                except Exception:
                    _uri = None
                if not _uri:
                    return ""
                return (
                    '<img src="{}" width="14" height="14" '
                    'style="vertical-align:middle;margin-right:4px;">'
                ).format(_uri)

            lc_icon_html = _icon_html_for(icon_name)
            rc_icon_html = _icon_html_for(rc.get("icon", ""))

            lc_tip = (data.get("tooltip") or data.get("name") or
                      "Button {}".format(i + 1)).strip()
            rc_tip = (rc.get("name") or "Right-click action").strip()
            tip_lines = []
            if lc_has_code:
                tip_lines.append("LC: {}{}".format(lc_icon_html, html.escape(lc_tip)))
            if rc_has_code:
                tip_lines.append("RC: {}{}".format(rc_icon_html, html.escape(rc_tip)))
            if not tip_lines:
                tip_lines.append(html.escape(lc_tip))

            pie_cmds = [c for c in (data.get("pie_commands") or [])
                        if (c.get("code") or "").strip()][:MAX_PIE_COMMANDS]
            if pie_cmds:
                tip_lines.append("")
                tip_lines.append("<b>Hold Left Click:</b>")
                for cmd in pie_cmds:
                    tip_lines.append("{}{}".format(
                        _icon_html_for(cmd.get("icon", "")),
                        html.escape((cmd.get("name") or "").strip() or "Command")))

            btn.setToolTip("<html>{}</html>".format("<br>".join(tip_lines)))
            btn.setVisible(visible)

        self._rebuild_quick_buttons_layout()

        # Resize panel to accommodate exactly the visible buttons
        if self._ui_built and self.isVisible():
            self._resize_to_content()

    def _on_quick_button(self, index):
        if index < 0 or index >= len(self.custom_buttons):
            return
        data      = self.custom_buttons[index]
        code_type = (data.get("type", "mel") or "mel").lower()
        code      = data.get("code", "") or ""
        if not code.strip():
            return
        self._prepare_command_execution(data)
        try:
            if code_type == "python":
                import __main__
                exec(code, __main__.__dict__)
            else:
                mel.eval(code)
        except Exception as e:
            cmds.warning("ModPanel quick button {} error: {}".format(index + 1, e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    def _on_quick_button_rc(self, index, btn_widget, pos):
        """Right-click on a quick button — runs its configured right-click
        action instantly, no confirmation menu. Independent of whatever the
        left-click side is doing.
        """
        if index < 0 or index >= len(self.quick_button_rc):
            return
        rc = self.quick_button_rc[index]
        if not (rc.get("code") or "").strip():
            return
        self._run_quick_rc(index)

    def _run_quick_rc(self, index):
        """Execute the right-click code for quick button at index."""
        if index < 0 or index >= len(self.quick_button_rc):
            return
        rc        = self.quick_button_rc[index]
        code      = (rc.get("code") or "").strip()
        code_type = (rc.get("type") or "python").lower()
        if not code:
            return
        data = self.custom_buttons[index] if index < len(self.custom_buttons) else None
        self._prepare_command_execution(data)
        try:
            if code_type == "python":
                import __main__
                exec(code, __main__.__dict__)
            else:
                mel.eval(code)
        except Exception as e:
            cmds.warning("ModPanel quick button {} RC error: {}".format(index + 1, e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    # ------------------------------------------------------------------
    # Grid
    # ------------------------------------------------------------------
    def clear_grid(self):
        for btn in self.button_widgets:
            try:
                btn.cleanup()
            except Exception:
                pass
        # Remove all row widgets (and spacer items) from the VBox
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.button_widgets.clear()

    def rebuild_grid(self):
        self.clear_grid()
        if not self.buttons_data:
            return

        from .widgets import PhoenixButtonWidget as _PBW

        base      = 64
        side      = int(base * self.button_scale * self.panel_scale)
        icon_size = int(side * 0.82)
        pad       = int(self.padding * self.panel_scale)
        cols      = self.cols

        pending  = []      # buttons accumulated between separators
        any_row  = [False] # whether grid_layout already has at least one item

        def _flush():
            """Lay out pending buttons as grid rows and clear the list."""
            if not pending:
                return
            total_p  = len(pending)
            num_rows = (total_p + cols - 1) // cols
            for r in range(num_rows):
                row_btns = pending[r * cols : (r + 1) * cols]
                is_partial = (r == num_rows - 1) and (total_p % cols != 0)
                align = (self.grid_row_alignment if is_partial
                         else self.grid_full_row_alignment)

                row_w = QtWidgets.QWidget()
                _theme.set_qss(row_w, "background: transparent;")
                rl = QtWidgets.QHBoxLayout(row_w)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.setSpacing(pad)
                self._apply_row_align(rl, row_btns, align)

                if any_row[0]:
                    self.grid_layout.addSpacing(pad)
                self.grid_layout.addWidget(row_w)
                any_row[0] = True
            pending.clear()

        for i, info in enumerate(self.buttons_data):
            if info.get("type") == "separator":
                continue   # separator feature removed — skip legacy entries
            overlay = info.get("label", "") or ""
            ann     = info.get("annotation", "") or ""
            icon_name = info.get("icon", "")
            icon    = self._resolve_info_icon(info, icon_size)
            btn = self._PhoenixButtonWidget(i, overlay, icon, ann,
                                            parent=self.grid_container)
            btn.set_theme(self.export_look_settings())
            btn.set_sizes(side, icon_size)
            btn.triggeredWithIndex.connect(self._on_button_triggered)
            btn.middleClickTriggered.connect(self._on_button_middle)
            btn.requestReposition.connect(self._enter_reposition_mode)
            btn.requestDelete.connect(self._on_button_delete)
            btn.requestEditLabel.connect(self._on_request_edit_label)
            btn.requestChangeIcon.connect(self._on_request_change_icon)
            btn.requestEditPie.connect(self._on_request_edit_pie)
            btn.requestAddToPie.connect(self._on_request_add_to_pie)
            btn.requestToggleCloseBehavior.connect(self._on_toggle_button_close_behavior)
            btn.pieCommandTriggered.connect(self._on_pie_command_triggered)
            btn.configure_pie(
                pie_provider=lambda idx: (
                    self.buttons_data[idx].get("pie_commands", [])
                    if idx < len(self.buttons_data) else []),
                angle_provider=lambda idx: (
                    self.buttons_data[idx].get("pie_start_angle")
                    if idx < len(self.buttons_data) else None),
                icon_resolver=self._resolve_pie_icon,
                main_icon_name=icon_name,
            )
            pending.append(btn)
            self.button_widgets.append(btn)

        _flush()
    @staticmethod
    def _apply_row_align(layout, widgets, alignment):
        """Add widgets to an HBoxLayout with the given alignment (0=L,1=C,2=R)."""
        if alignment == 0:    # Left
            for w in widgets:
                layout.addWidget(w)
            layout.addStretch(1)
        elif alignment == 2:  # Right
            layout.addStretch(1)
            for w in widgets:
                layout.addWidget(w)
        else:                 # Center
            layout.addStretch(1)
            for w in widgets:
                layout.addWidget(w)
            layout.addStretch(1)

    # ------------------------------------------------------------------
    # Button operations
    # ------------------------------------------------------------------
    def _on_button_delete(self, index):
        if 0 <= index < len(self.buttons_data):
            self.buttons_data.pop(index)
            self._grid_dirty = True
            self.rebuild_grid()
            self.save_tab_config(self.current_tab)

    # ------------------------------------------------------------------
    # REPOSITION MODE  (panel owns all drag state)
    # ------------------------------------------------------------------
    def _enter_reposition_mode(self, src_index):
        """Activate reposition mode. Style all buttons, install app filter.
        Drag does not start until the user clicks a button (handled in
        _reposition_event_filter idle state).
        """
        if self._reposition_mode:
            return  # already active

        self._reposition_mode = True
        self._drag_src_index  = None   # idle — no button picked up yet
        self._drag_dst_index  = None

        # Style all buttons as reposition-idle (dashed border) — skip separators
        for btn in self.button_widgets:
            if hasattr(btn, "_reposition_idle_style"):
                btn._reposition_idle_style()

        # Immediately start dragging the button that was right-clicked
        src_btn = self.button_widgets[src_index] if 0 <= src_index < len(self.button_widgets) else None
        if src_btn:
            centre = src_btn.mapToGlobal(src_btn.rect().center())
            self._start_drag_on(src_index, centre)

        # Install app-level filter to track ALL mouse events
        app = QtWidgets.QApplication.instance()
        if app:
            app.installEventFilter(self)

    def _reposition_event_filter(self, evt):
        """Full state-machine for reposition mode mouse events.

        States:
          _drag_src_index is None  → idle (waiting for a click on a button)
          _drag_src_index is set   → actively dragging that button

        Returns True to consume the event, False to pass through.
        """
        t = evt.type()

        # ── IDLE: waiting for user to click a button to drag ──────────
        if self._drag_src_index is None:

            if t == QtCore.QEvent.MouseButtonPress:
                try:
                    gpos = evt.globalPos()
                except AttributeError:
                    gpos = evt.globalPosition().toPoint()

                # Outside the panel → exit reposition mode, close panel
                # Use frameGeometry() — it's in screen coords for a top-level window
                if not self.frameGeometry().contains(gpos):
                    self._cancel_reposition()
                    self.hide()
                    return True

                # Find which button was clicked
                from .widgets import PhoenixButtonWidget as _PBW
                widget_under = QtWidgets.QApplication.widgetAt(gpos)
                clicked_index = None
                w = widget_under
                for _ in range(8):
                    if w is None:
                        break
                    if isinstance(w, _PBW):
                        try:
                            clicked_index = self.button_widgets.index(w)
                        except ValueError:
                            clicked_index = w.index
                        break
                    w = w.parent() if hasattr(w, "parent") else None

                if clicked_index is not None:
                    # Start dragging this button
                    self._start_drag_on(clicked_index, gpos)
                    return True

                # Clicked inside panel but not on a button — ignore
                return True

            elif t == QtCore.QEvent.MouseButtonRelease:
                # Always consume releases in idle state so tool_btn.clicked never fires
                return True

            elif t == QtCore.QEvent.KeyPress:
                if evt.key() == QtCore.Qt.Key_Escape:
                    self._cancel_reposition()
                    return True

            return False  # pass through non-mouse events

        # ── DRAGGING: button picked up, tracking mouse ─────────────────
        if t == QtCore.QEvent.MouseMove:
            try:
                gpos = evt.globalPos()
            except AttributeError:
                gpos = evt.globalPosition().toPoint()
            self._reposition_mouse_move(gpos)
            return True

        elif t == QtCore.QEvent.MouseButtonRelease:
            if evt.button() == QtCore.Qt.LeftButton:
                self._commit_reposition()
                return True

        elif t == QtCore.QEvent.KeyPress:
            if evt.key() == QtCore.Qt.Key_Escape:
                self._cancel_reposition()
                return True

        return False

    def _start_drag_on(self, src_index, global_pos):
        """Pick up the button at src_index and start dragging it."""
        from .widgets import _GhostLabel

        if not (0 <= src_index < len(self.button_widgets)):
            return

        self._drag_src_index = src_index
        self._drag_dst_index = src_index

        # Build ghost
        src_btn = self.button_widgets[src_index]
        pm = src_btn.grab()
        if self._drag_ghost:
            self._drag_ghost.hide()
            self._drag_ghost.deleteLater()
        self._drag_ghost = _GhostLabel(pm)
        self._drag_ghost.move_center_to(global_pos)
        self._drag_ghost.show()

        if hasattr(src_btn, "_dragging_source_style"):
            src_btn._dragging_source_style()

    def _reposition_mouse_move(self, global_pos):
        """Move ghost and update live order preview."""
        if self._drag_ghost:
            self._drag_ghost.move_center_to(global_pos)

        # Hit-test: hide ghost temporarily so widgetAt sees through it
        if self._drag_ghost:
            self._drag_ghost.hide()
        widget_under = QtWidgets.QApplication.widgetAt(global_pos)
        if self._drag_ghost:
            self._drag_ghost.show()

        # Walk widget tree to find a PhoenixButtonWidget under the cursor
        from .widgets import PhoenixButtonWidget as _PBW
        target_index = None
        w = widget_under
        for _ in range(8):
            if w is None:
                break
            if isinstance(w, _PBW):
                try:
                    target_index = self.button_widgets.index(w)
                except ValueError:
                    target_index = w.index
                break
            w = w.parent() if hasattr(w, "parent") else None

        if target_index is None or target_index == self._drag_src_index:
            # Not over a valid target — clear previous highlight
            if self._drag_dst_index != self._drag_src_index:
                if 0 <= self._drag_dst_index < len(self.button_widgets):
                    w = self.button_widgets[self._drag_dst_index]
                    if hasattr(w, "_reposition_idle_style"):
                        w._reposition_idle_style()
            self._drag_dst_index = self._drag_src_index
            return

        if target_index == self._drag_dst_index:
            return

        # Clear old target highlight
        if (self._drag_dst_index != self._drag_src_index and
                0 <= self._drag_dst_index < len(self.button_widgets)):
            w = self.button_widgets[self._drag_dst_index]
            if hasattr(w, "_reposition_idle_style"):
                w._reposition_idle_style()

        self._drag_dst_index = target_index

        # Live-shuffle data + widgets
        self._live_swap(self._drag_src_index, target_index)
        self._drag_src_index = target_index

        # Highlight new slot
        if 0 <= target_index < len(self.button_widgets):
            w = self.button_widgets[target_index]
            if hasattr(w, "_drop_target_style"):
                w._drop_target_style()

    def _live_swap(self, src, dst):
        """Move data and widgets from src to dst without destroying anything."""
        if src == dst:
            return
        if not (0 <= src < len(self.buttons_data) and 0 <= dst < len(self.buttons_data)):
            return

        # Move data
        item = self.buttons_data.pop(src)
        self.buttons_data.insert(dst, item)

        # Move widget reference
        widget = self.button_widgets.pop(src)
        self.button_widgets.insert(dst, widget)

        # Update .index on PhoenixButtonWidgets (separators have no .index)
        for i, btn in enumerate(self.button_widgets):
            if hasattr(btn, "index"):
                btn.index = i

        # Reflow: rebuild row widgets in the VBox
        self._reflow_grid_widgets()

        # Style: source slot shows drag style, rest idle
        for i, btn in enumerate(self.button_widgets):
            if i == dst:
                if hasattr(btn, "_dragging_source_style"):
                    btn._dragging_source_style()
            else:
                if hasattr(btn, "_reposition_idle_style"):
                    btn._reposition_idle_style()

    def _reflow_grid_widgets(self):
        """Rebuild VBox row layout from current button_widgets order (no widget recreation)."""
        from .widgets import PhoenixButtonWidget as _PBW

        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        pad      = self.padding
        cols     = self.cols
        pending  = []
        any_row  = [False]

        def _flush():
            if not pending:
                return
            total_p  = len(pending)
            num_rows = (total_p + cols - 1) // cols
            for r in range(num_rows):
                row_btns = pending[r * cols : (r + 1) * cols]
                is_partial = (r == num_rows - 1) and (total_p % cols != 0)
                align = (self.grid_row_alignment if is_partial
                         else self.grid_full_row_alignment)
                row_w = QtWidgets.QWidget()
                _theme.set_qss(row_w, "background: transparent;")
                rl = QtWidgets.QHBoxLayout(row_w)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.setSpacing(pad)
                self._apply_row_align(rl, row_btns, align)
                if any_row[0]:
                    self.grid_layout.addSpacing(pad)
                self.grid_layout.addWidget(row_w)
                any_row[0] = True
            pending.clear()

        for w in self.button_widgets:
            if isinstance(w, _PBW):
                pending.append(w)
            # non-PBW items (legacy separators) are silently skipped

        _flush()

    def _commit_reposition(self):
        """Mouse released — save order, reset to idle, stay in reposition mode.
        User can now click any other button to drag it.
        """
        self._grid_dirty = False  # reflow already kept grid in sync
        self.save_tab_config(self.current_tab)

        if self._drag_ghost:
            self._drag_ghost.hide()
            self._drag_ghost.deleteLater()
            self._drag_ghost = None

        self._drag_src_index = None   # back to idle state
        self._drag_dst_index = None

        # All buttons return to reposition-idle style
        for btn in self.button_widgets:
            if hasattr(btn, "_reposition_idle_style"):
                btn._reposition_idle_style()

    def _cancel_reposition(self):
        """Escape or panel close — exit reposition mode entirely."""
        self._reposition_mode = False
        self._drag_src_index  = None
        self._drag_dst_index  = None

        if self._drag_ghost:
            self._drag_ghost.hide()
            self._drag_ghost.deleteLater()
            self._drag_ghost = None

        app = QtWidgets.QApplication.instance()
        if app:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass

        for btn in self.button_widgets:
            if hasattr(btn, "_normal_style"):
                btn._normal_style()

    def _exit_reposition_mode(self):
        """Alias used on panel close."""
        if self._reposition_mode:
            self._cancel_reposition()

    def _effective_close_on_click(self, button_info=None):
        """Return the effective close-after-command state for one button.

        ``close_on_click`` is the shared default.  A button can opt into
        ``invert_close_on_click`` which deliberately flips that global state:
        global ON -> this button stays open; global OFF -> this button closes.
        """
        should_close = bool(getattr(self, "close_on_click", True))
        if isinstance(button_info, dict) and bool(
                button_info.get("invert_close_on_click", False)):
            should_close = not should_close
        return should_close

    def _prepare_command_execution(self, button_info=None):
        """Arm the short dismiss guard and hide immediately when required.

        Hiding before the command runs also handles commands that open a modal
        UI and do not return until that UI closes.
        """
        self._ignore_close = True
        if self._effective_close_on_click(button_info):
            self.hide()

    def _on_button_middle(self, index):
        """Execute the double-click command stored on a button (middle-click)."""
        if index < 0 or index >= len(self.buttons_data):
            return
        info = self.buttons_data[index]
        cmd  = (info.get("doubleClickCommand") or "").strip()
        if not cmd:
            return   # no secondary command — silently do nothing
        src = (
            info.get("doubleClickSourceType") or
            info.get("sourceType") or
            "mel"
        ).lower()
        self._prepare_command_execution(info)
        try:
            if src == "python":
                import __main__
                exec(cmd, __main__.__dict__)
            else:
                mel.eval(cmd)
        except Exception as e:
            cmds.warning("ModPanel middle-click: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    def _on_button_triggered(self, index):
        if index < 0 or index >= len(self.buttons_data):
            return
        info = self.buttons_data[index]
        if info.get("type") == "separator":
            return
        cmd  = info.get("command", "")
        src  = (info.get("sourceType", "mel") or "mel").lower()
        if not cmd:
            return
        # Track in recent commands (if enabled)
        if self.recent_commands_enabled:
            self._add_to_recent(info)
        self._prepare_command_execution(info)
        try:
            if src == "python":
                import __main__
                exec(cmd, __main__.__dict__)
            else:
                mel.eval(cmd)
        except Exception as e:
            cmds.warning("ModPanel: Error executing button: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    def _rearm_dismiss(self):
        self._ignore_close = False

    # ------------------------------------------------------------------
    # Pie-menu system: execution
    # ------------------------------------------------------------------
    def _execute_pie_command(self, cmd, recent_source=None, button_info=None):
        """Run one pie command using its source button's close behaviour."""
        if not isinstance(cmd, dict):
            return
        code = (cmd.get("code") or "").strip()
        if not code:
            return
        code_type = (cmd.get("type") or "mel").lower()
        if recent_source is not None and self.recent_commands_enabled:
            if isinstance(button_info, dict):
                recent_source["invert_close_on_click"] = bool(
                    button_info.get("invert_close_on_click", False))
            self._add_to_recent(recent_source)
        self._prepare_command_execution(button_info)
        try:
            if code_type == "python":
                import __main__
                exec(code, __main__.__dict__)
            else:
                mel.eval(code)
        except Exception as e:
            cmds.warning("ModPanel pie command: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    @staticmethod
    def _pie_cmd_to_recent(cmd):
        return {
            "label":      cmd.get("name", ""),
            "annotation": cmd.get("tooltip", ""),
            "icon":       cmd.get("icon", ""),
            "icon_candidates": list(cmd.get("icon_candidates", []) or []),
            "command":    cmd.get("code", ""),
            "sourceType": cmd.get("type", "mel"),
        }

    def _on_pie_command_triggered(self, index, cmd):
        """A regular panel button's pie menu selected `cmd`."""
        info = self.buttons_data[index] if 0 <= index < len(self.buttons_data) else None
        self._execute_pie_command(
            cmd, recent_source=self._pie_cmd_to_recent(cmd), button_info=info)

    def _on_hotbutton_pie_selected(self, index, cmd):
        """A hot (title-bar) button's pie menu selected `cmd`."""
        info = self.custom_buttons[index] if 0 <= index < len(self.custom_buttons) else None
        self._execute_pie_command(
            cmd, recent_source=self._pie_cmd_to_recent(cmd), button_info=info)

    def _on_toggle_button_close_behavior(self, index):
        """Flip this panel button's inverse close-on-click override."""
        if index < 0 or index >= len(self.buttons_data):
            return
        info = self.buttons_data[index]
        info["invert_close_on_click"] = not bool(
            info.get("invert_close_on_click", False))
        self.save_tab_config(self.current_tab)

    # ------------------------------------------------------------------
    # Pie-menu system: direct editing ("Edit Pie Commands")
    # ------------------------------------------------------------------
    def _on_request_edit_label(self, index):
        """Panel button context-menu: 'Edit Label' — the short overlay text
        drawn across the bottom of the button's icon."""
        if index < 0 or index >= len(self.buttons_data):
            return
        info = self.buttons_data[index]
        current = (info.get("label") or "").strip()
        self._ignore_close = True
        try:
            new_text, ok = QtWidgets.QInputDialog.getText(
                self, "Edit Label",
                "Label shown across the bottom of this button's icon "
                "(leave blank for none):",
                QtWidgets.QLineEdit.Normal, current)
        finally:
            self._ignore_close = False
        if not ok:
            return
        new_text = (new_text or "").strip()
        info["label"] = new_text
        self.save_tab_config(self.current_tab)
        if index < len(self.button_widgets):
            self.button_widgets[index].set_overlay_label(new_text)

    def _on_request_change_icon(self, index, source):
        """Change only a panel button's icon, leaving its commands and every
        other setting untouched. ``source`` is shelf, local, or clear.
        """
        if index < 0 or index >= len(self.buttons_data):
            return

        icon_name = None
        icon_candidates = []
        if source == "shelf":
            try:
                Picker = _get_shelf_picker()
                dlg = Picker(parent=self)
                dlg.list_widget.setSelectionMode(
                    QtWidgets.QAbstractItemView.SingleSelection)
                accepted = dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
                if accepted != QtWidgets.QDialog.Accepted:
                    return
                selected = dlg.selected_buttons()
                if not selected:
                    return
                selected_icon = selected[0]
                icon_name = selected_icon.get("icon", "") or ""
                icon_candidates = list(selected_icon.get("icon_candidates", []) or [])
            except Exception as e:
                cmds.warning("ModPanel: could not choose shelf icon: {}".format(e))
                return
        elif source == "local":
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Choose Button Icon", "",
                "Images (*.png *.svg *.xpm *.bmp *.jpg *.jpeg *.gif);;All Files (*)")
            if not path:
                return
            icon_name = path
        elif source == "clear":
            icon_name = ""
        else:
            return

        info = self.buttons_data[index]
        info["icon"] = icon_name
        if icon_candidates:
            info["icon_candidates"] = icon_candidates
        else:
            info.pop("icon_candidates", None)
        self.save_tab_config(self.current_tab)

        # Update the live widget directly; no grid rebuild or unrelated state
        # changes are needed. Search mode can make button_widgets compact, so
        # find by the widget's original data index instead of list position.
        target = None
        for widget in self.button_widgets:
            if getattr(widget, "index", None) == index:
                target = widget
                break
        if target is not None:
            size = max(1, target.tool_btn.iconSize().width())
            target.tool_btn.setIcon(
                self._resolve_info_icon(info, size) if icon_name or icon_candidates
                else QtGui.QIcon())
            target._main_icon_name = icon_name
            target.refresh_tooltip()

    def _on_request_edit_pie(self, index):
        """Panel button context-menu: 'Edit Pie Commands'."""
        if index < 0 or index >= len(self.buttons_data):
            return
        info = self.buttons_data[index]
        title = "Edit Pie Commands — {}".format(
            (info.get("label") or info.get("name") or "Button").strip())

        def _get():
            return info.get("pie_commands", [])

        def _set(new_list):
            info["pie_commands"] = new_list
            self.save_tab_config(self.current_tab)
            if index < len(self.button_widgets):
                self.button_widgets[index].refresh_tooltip()

        def _get_angle():
            return info.get("pie_start_angle")

        def _set_angle(value):
            info["pie_start_angle"] = value
            self.save_tab_config(self.current_tab)

        self._open_pie_editor(title, _get, _set, get_angle=_get_angle, set_angle=_set_angle)

    def _open_pie_editor(self, title, get_pies, set_pies, get_angle=None, set_angle=None):
        self._ignore_close = True
        try:
            from .pie_editor import PieCommandEditorDialog
            dlg = PieCommandEditorDialog(
                self, title, get_pies, set_pies,
                icon_resolver=self._resolve_pie_icon,
                get_angle=get_angle, set_angle=set_angle)
            dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        except Exception as e:
            cmds.warning("ModPanel: could not open pie editor: {}".format(e))
        finally:
            self._ignore_close = False

    # ------------------------------------------------------------------
    # Pie-menu system: "Add to Another Button's Pie"
    # ------------------------------------------------------------------
    def _on_request_add_to_pie(self, index):
        """Panel button context-menu: 'Add to Another Button's Pie'."""
        if index < 0 or index >= len(self.buttons_data):
            return
        info = self.buttons_data[index]
        if not (info.get("command") or "").strip():
            cmds.warning("ModPanel: this button has no command to add to a pie.")
            return
        self._show_add_to_pie_picker(("panel", index))

    def _show_add_to_pie_picker(self, source_ref):
        """Visual picker: shows the 10 hot buttons and every button in the
        current tab as clickable icons — the same buttons the user already
        knows from the panel itself — instead of a plain text list. Toggle
        any number of buttons on, then Add applies the source command to
        all of them at once; Cancel or Escape backs out without changing
        anything."""
        has_hot_dest = any(("hot", i) != source_ref for i in range(len(self.custom_buttons)))
        has_panel_dest = any(
            info.get("type") != "separator" and ("panel", i) != source_ref
            for i, info in enumerate(self.buttons_data)
        )
        if not has_hot_dest and not has_panel_dest:
            cmds.warning("ModPanel: no other buttons available as a pie destination.")
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Add to Another Button's Pie")
        dlg.resize(520, 480)
        _theme.set_qss(dlg, "background:#1b1e29; color:#dfe3ff;")
        outer = QtWidgets.QVBoxLayout(dlg)

        hint = QtWidgets.QLabel(
            "Select one or more buttons to add this command to their pie menu.")
        hint.setWordWrap(True)
        _theme.set_qss(hint, "color:#8894c0; font-size:10px; margin-bottom:2px;")
        outer.addWidget(hint)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        _theme.set_qss(scroll, "QScrollArea { border: none; background: transparent; }")
        inner = QtWidgets.QWidget()
        _theme.set_qss(inner, "background: transparent;")
        inner_lay = QtWidgets.QVBoxLayout(inner)
        inner_lay.setSpacing(12)

        selected_refs = set()

        _NORMAL_SS = """
        QToolButton {
            background:#202432; border:1px solid #33395a; border-radius:9px;
        }
        QToolButton:hover { background:#28304a; border-color:#5a90d0; }
        """
        _SELECTED_SS = """
        QToolButton {
            background:#1e3050; border:2px solid #5a90d0; border-radius:9px;
        }
        QToolButton:hover { background:#28304a; }
        """

        def _section_label(text):
            lb = QtWidgets.QLabel(text)
            _theme.set_qss(lb, "color:#7fa8d8; font-size:10px; font-weight:bold;")
            return lb

        def _update_add_label():
            n = len(selected_refs)
            add_btn.setText("Add to {} Selected".format(n) if n else "Add")
            add_btn.setEnabled(n > 0)

        def _on_toggle(ref, btn, checked):
            if checked:
                selected_refs.add(ref)
                _theme.set_qss(btn, _SELECTED_SS)
            else:
                selected_refs.discard(ref)
                _theme.set_qss(btn, _NORMAL_SS)
            _update_add_label()

        def _make_icon_btn(icon_name, tooltip_text, ref):
            b = QtWidgets.QToolButton()
            b.setFixedSize(42, 42)
            b.setIconSize(QtCore.QSize(26, 26))
            if icon_name:
                b.setIcon(self._resolve_maya_icon(icon_name))
            b.setToolTip(tooltip_text)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setCheckable(True)
            _theme.set_qss(b, _NORMAL_SS)
            b.toggled.connect(lambda checked, r=ref, btn=b: _on_toggle(r, btn, checked))
            return b

        def _flow_grid(pairs, columns):
            """pairs: list of (icon_name, tooltip, ref). Lays out as a
            wrapping grid with the given column count."""
            grid = QtWidgets.QGridLayout()
            grid.setSpacing(6)
            r = c = 0
            for icon_name, tip, ref in pairs:
                grid.addWidget(_make_icon_btn(icon_name, tip, ref), r, c)
                c += 1
                if c >= columns:
                    c = 0
                    r += 1
            return grid

        if has_hot_dest:
            inner_lay.addWidget(_section_label("HOT BUTTONS"))
            hot_pairs = []
            for i, hb in enumerate(self.custom_buttons):
                ref = ("hot", i)
                if ref == source_ref:
                    continue
                name = (hb.get("name") or "").strip() or "BTN{}".format(i + 1)
                # Real configured tooltip first, falling back to the name —
                # previously this showed the name twice and never the
                # actual tooltip text the user set for the button.
                tip_text = (hb.get("tooltip") or "").strip() or name
                hot_pairs.append((hb.get("icon", ""), "Hot Button {}: {}".format(i + 1, tip_text), ref))
            inner_lay.addLayout(_flow_grid(hot_pairs, 10))

        if has_panel_dest:
            inner_lay.addWidget(_section_label("PANEL BUTTONS"))
            panel_pairs = []
            for i, info in enumerate(self.buttons_data):
                if info.get("type") == "separator":
                    continue
                ref = ("panel", i)
                if ref == source_ref:
                    continue
                label = (info.get("label") or info.get("name") or "").strip() or "Button {}".format(i + 1)
                # Real annotation first (what the panel button's own tooltip
                # actually shows), falling back to its label.
                tip_text = (info.get("annotation") or "").strip() or label
                panel_pairs.append((info.get("icon", ""), tip_text, ref))
            inner_lay.addLayout(_flow_grid(panel_pairs, 10))

        inner_lay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        btn_row = QtWidgets.QHBoxLayout()
        cancel_btn = QtWidgets.QPushButton("Cancel")
        add_btn    = QtWidgets.QPushButton("Add")
        for b in (cancel_btn, add_btn):
            _theme.set_qss(b, """
            QPushButton {
                background:#252a39; color:#c8d2ff; border:1px solid #3a4060;
                border-radius:4px; padding:4px 14px; font-size:10px;
            }
            QPushButton:hover { background:#2e3448; }
            QPushButton:disabled { color:#5c6688; border-color:#2a3050; background:#1c2030; }
            """)
        add_btn.setEnabled(False)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(add_btn)
        outer.addLayout(btn_row)

        def _confirm():
            dlg.accept()
            for ref in list(selected_refs):
                self._add_source_to_pie(source_ref, ref)

        add_btn.clicked.connect(_confirm)
        cancel_btn.clicked.connect(dlg.reject)

        self._ignore_close = True
        try:
            dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        finally:
            self._ignore_close = False

    def _add_source_to_pie(self, src_ref, dest_ref):
        """Copy the primary command of the button at `src_ref` into the
        first available pie slot of the button at `dest_ref`."""
        if dest_ref == src_ref:
            cmds.warning("ModPanel: can't add a button to its own pie.")
            return

        src_kind, src_idx = src_ref
        if src_kind == "panel":
            if not (0 <= src_idx < len(self.buttons_data)):
                return
            s = self.buttons_data[src_idx]
            src_cmd = {
                "name":    (s.get("label") or s.get("name") or "").strip(),
                "tooltip": s.get("annotation", ""),
                "type":    (s.get("sourceType", "mel") or "mel").lower(),
                "code":    s.get("command", ""),
                "icon":    s.get("icon", ""),
                "icon_candidates": list(s.get("icon_candidates", []) or []),
            }
        else:
            if not (0 <= src_idx < len(self.custom_buttons)):
                return
            s = self.custom_buttons[src_idx]
            src_cmd = {
                "name":    (s.get("name") or "").strip(),
                "tooltip": s.get("tooltip", ""),
                "type":    (s.get("type", "mel") or "mel").lower(),
                "code":    s.get("code", ""),
                "icon":    s.get("icon", ""),
                "icon_candidates": list(s.get("icon_candidates", []) or []),
            }

        if not src_cmd["code"].strip():
            cmds.warning("ModPanel: source button has no command to add.")
            return

        dst_kind, dst_idx = dest_ref
        if dst_kind == "panel":
            if not (0 <= dst_idx < len(self.buttons_data)):
                return
            dst_pies = _sanitize_pie_commands(self.buttons_data[dst_idx].get("pie_commands", []))
        else:
            if not (0 <= dst_idx < len(self.custom_buttons)):
                return
            dst_pies = _sanitize_pie_commands(self.custom_buttons[dst_idx].get("pie_commands", []))

        if len(dst_pies) >= MAX_PIE_COMMANDS:
            cmds.warning("ModPanel: this button already contains the "
                         "maximum of six pie commands.")
            return

        for existing in dst_pies:
            if (existing.get("code", "") == src_cmd["code"] and
                    existing.get("type", "") == src_cmd["type"]):
                cmds.warning("ModPanel: that command is already in this "
                             "button's pie.")
                return

        dst_pies.append(src_cmd)

        if dst_kind == "panel":
            self.buttons_data[dst_idx]["pie_commands"] = dst_pies
            self.save_tab_config(self.current_tab)
            if dst_idx < len(self.button_widgets):
                self.button_widgets[dst_idx].refresh_tooltip()
            cmds.inViewMessage(
                amg="Added to <hl>Panel Button</hl> pie", pos="topCenter", fade=True)
        else:
            self.custom_buttons[dst_idx]["pie_commands"] = dst_pies
            self.save_global_state()
            self.update_quick_buttons()
            cmds.inViewMessage(
                amg="Added to <hl>Hot Button {}</hl> pie".format(dst_idx + 1),
                pos="topCenter", fade=True)

    # ------------------------------------------------------------------
    # Pie-menu system: cleanup
    # ------------------------------------------------------------------
    def _cancel_all_active_pies(self):
        """Force-close any open pie popup — called whenever the panel is
        hidden or closed so a held pie never outlives its host window."""
        for w in getattr(self, "button_widgets", []):
            if hasattr(w, "cancel_active_pie"):
                try:
                    w.cancel_active_pie()
                except Exception:
                    pass
        for w in getattr(self, "quick_buttons", []):
            if hasattr(w, "cancel_active_pie"):
                try:
                    w.cancel_active_pie()
                except Exception:
                    pass

    def _reload_phoenix_panel(self, reopen=True):
        """Hot-reload PhoenixPanel, optionally reopening the fresh instance.

        ``reopen`` lets the title double-click respect Close on click without
        sacrificing the existing reload behaviour when that setting is off.
        """
        cmds.inViewMessage(amg="Reloading <hl>ModPanel</hl>...",
                            pos="topCenter", fade=True)
        QtCore.QTimer.singleShot(
            0, lambda _reopen=bool(reopen): _do_phoenix_panel_reload(_reopen))

    # ------------------------------------------------------------------
    # Settings / Shelf picker
    # ------------------------------------------------------------------
    def open_settings_window(self):
        self._ignore_close = True
        try:
            win = getattr(self, "settings_win", None)
            alive = win is not None
            if alive:
                try:
                    win.isVisible()
                except RuntimeError:
                    alive = False

            if not alive:
                SettingsClass = _get_settings()
                win = SettingsClass(parent=self, panel=self)
                self.settings_win = win
                win.settingsChanged.connect(self._settings_updated)
                win.finished.connect(
                    lambda *_: setattr(self, "_ignore_close", False)
                )
            else:
                win.refresh_from_panel()

            win.show()
            win.raise_()
            win.activateWindow()
        except Exception:
            import traceback
            cmds.warning(
                "ModPanel: settings failed to open:\n" +
                traceback.format_exc()
            )
            self._ignore_close = False

    def _settings_updated(self):
        self._apply_panel_scale()
        self._grid_dirty = True
        self.rebuild_grid()
        self.update_quick_buttons()
        self._update_title_tab_hint()
        self._rebuild_title_tooltip()
        self.save_tab_config(self.current_tab)
        if self._ui_built and self.isVisible():
            self._resize_to_content()

    def _apply_panel_scale(self):
        """Re-apply panel_scale to the STATIC chrome built once in
        _build_ui() (main margins/spacing, title font, hot-button row
        height) — everything else (button grid, hot-button sizes, window
        size) already reads panel_scale fresh every time it's recomputed,
        via rebuild_grid()/update_quick_buttons()/_compute_ideal_size()."""
        if not getattr(self, "_ui_built", False):
            return
        ps = self.panel_scale
        hbs = self.hot_button_icon_scale
        if getattr(self, "_main_layout", None) is not None:
            m = int(10 * ps)
            self._main_layout.setContentsMargins(m, m, m, m)
            self._main_layout.setSpacing(int(8 * ps))
        if hasattr(self, "quick_buttons_frame"):
            self.quick_buttons_frame.setFixedHeight(int(26 * ps * hbs))
        if hasattr(self, "quick_buttons_layout"):
            self.quick_buttons_layout.setContentsMargins(int(4 * ps), 0, int(4 * ps), 0)

        if hasattr(self, "add_btn"):
            self.add_btn.setFixedHeight(int(24 * ps))
            _theme.set_qss(self.add_btn, """
            QPushButton {{
                background: #252a39;
                color: #c8d2ff;
                border-radius: 6px;
                padding: {padv}px {padh}px;
                font-size: {fs}px;
            }}
            QPushButton:hover {{ background: #2f3547; }}
            """.format(padv=int(2 * ps), padh=int(8 * ps), fs=int(11 * ps)))
        if hasattr(self, "settings_btn"):
            self.settings_btn.setFixedSize(int(26 * ps), int(26 * ps))
            _theme.set_qss(self.settings_btn, """
                QPushButton {{
                    background: #252a39;
                    color: #c8d2ff;
                    border-radius: 6px;
                    font-size: {fs}px;
                }}
                QPushButton:hover {{ background: #32384c; }}
            """.format(fs=int(14 * ps)))
        if hasattr(self, "_pin_btn"):
            self._pin_btn.setFixedSize(int(26 * ps), int(26 * ps))
            _theme.set_qss(self._pin_btn, """
                QPushButton {
                    background: #252a39; border: none; border-radius: 6px;
                }
                QPushButton:hover    { background: #32384c; }
                QPushButton:checked  { background: #2a3a5a; }
            """)
            self._refresh_pin_icon()
        if hasattr(self, "_title_label"):
            _theme.set_qss(self._title_label, "color: #f5f7ff; font-weight: bold; font-size: {}px;".format(int(12 * ps)))
        # Re-apply the active Look after the legacy sizing code above so a
        # live scale change never resets custom colours or radii.
        self._apply_look_theme()

    def open_shelf_picker(self):
        ShelfPickerClass = _get_shelf_picker()
        dlg = ShelfPickerClass(parent=self)
        self._ignore_close = True
        result = dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        self._ignore_close = False
        if result != QtWidgets.QDialog.Accepted:
            return
        items = dlg.selected_buttons()
        if not items:
            return
        self.buttons_data.extend(items)
        self._grid_dirty = True
        self.rebuild_grid()
        self.save_tab_config(self.current_tab)

    # ------------------------------------------------------------------
    # Drag-and-drop import from Maya's shelf (MMB-drag a shelf button onto
    # the panel while pinned)
    # ------------------------------------------------------------------
    # Maya's shelf-button drag (started with a middle-mouse-button drag on a
    # shelf icon, exactly like dragging one shelf button onto another) is
    # NOT a standard Qt QDrag/QMimeData operation — it's Maya's own internal
    # drag-and-drop system. The only Autodesk-supported way for a custom UI
    # to receive it is a genuine Maya-native control with a registered
    # dropCallback. Our panel is a plain floating PySide window, not a Maya
    # control, so we bridge one in: create a tiny native formLayout in a
    # hidden host window, register the dropCallback on it, then reparent its
    # underlying Qt widget into our own panel. The callback's `dragControl`
    # argument is the actual shelfButton control name being dragged, which
    # we can query directly with cmds.shelfButton(...) — the exact same
    # extraction shelf_picker.py already does for the manual picker.
    def _setup_shelf_drop_zone(self):
        if getattr(self, "_shelf_drop_widget", None) is not None:
            return
        try:
            import maya.OpenMayaUI as omui
            try:
                import shiboken6 as shiboken
            except ImportError:
                import shiboken2 as shiboken

            win_name = "phoenixPanelDropHostWin"
            if cmds.window(win_name, exists=True):
                cmds.deleteUI(win_name)
            cmds.window(win_name, widthHeight=(1, 1))
            form_name = cmds.formLayout(parent=win_name)
            cmds.control(form_name, edit=True, dropCallback=self._on_native_shelf_drop)

            ptr = omui.MQtUtil.findControl(form_name)
            if not ptr:
                self._shelf_drop_widget = None
                return
            native_widget = shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)
            native_widget.setParent(self)
            native_widget.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
            _theme.set_qss(native_widget, "background: transparent;")
            native_widget.setGeometry(0, 0, self.width(), self.height())
            native_widget.lower()   # sit behind the visible buttons — normal
                                     # clicks still hit them first; this only
                                     # needs to exist as a registered drop
                                     # target, not to intercept normal input.
            native_widget.show()
            self._shelf_drop_widget = native_widget
            self._shelf_drop_window = win_name
        except Exception:
            self._shelf_drop_widget = None

    def _on_native_shelf_drop(self, dragControl, dropControl, messages, x, y, dragType):
        # Deliberately scoped to pinned mode only, per how this feature was
        # asked for — a popped-up (unpinned) panel is more transient and
        # this keeps the interaction predictable.
        if not self._pinned:
            return
        if dragType != "button":
            return
        if not dragControl or not cmds.shelfButton(dragControl, exists=True):
            return
        info = self._shelf_button_info_from_control(dragControl)
        if info is None:
            return
        # Imports into whichever tab is currently active/showing — e.g. if
        # tab "1" is on screen, it lands in tab 1.
        self.buttons_data.append(info)
        self._grid_dirty = True
        self.rebuild_grid()
        self.save_tab_config(self.current_tab)
        try:
            cmds.inViewMessage(
                amg="Imported <hl>{}</hl> into this panel".format(
                    info.get("label") or info.get("name") or "shelf button"),
                pos="topCenter", fade=True)
        except Exception:
            pass

    def _shelf_button_info_from_control(self, full_path, fast_annotation=None):
        """Query a shelfButton control directly by name and build the same
        info dict shape ShelfPickerDialog.selected_buttons() produces.

        `fast_annotation`, if given, is used in place of the annotation
        query — every caller already reads the widget's own .toolTip()
        (free, no Maya round-trip) before getting here, and Maya's shelf
        buttons set that directly from the annotation, so this skips one
        of the seven cmds.shelfButton() round-trips this would otherwise
        need. Falls back to the real query if it's empty/unavailable.

        Existence is intentionally NOT re-checked here — every call site
        already verifies cmds.shelfButton(full_path, exists=True) before
        calling this, so re-checking would just be a wasted round-trip.
        """
        try:
            label      = cmds.shelfButton(full_path, q=True, label=True) or ""
            if fast_annotation:
                ann = fast_annotation
            else:
                ann = cmds.shelfButton(full_path, q=True, annotation=True) or ""
            icon_label = cmds.shelfButton(full_path, q=True, imageOverlayLabel=True) or ""
            icon_candidates = self._shelf_button_icon_names(full_path)
            icon       = icon_candidates[0] if icon_candidates else ""
            command    = cmds.shelfButton(full_path, q=True, command=True) or ""
            src        = cmds.shelfButton(full_path, q=True, sourceType=True) or "mel"
            dbl_cmd    = cmds.shelfButton(full_path, q=True, doubleClickCommand=True) or ""
        except Exception:
            return None

        overlay = icon_label.strip() if icon_label and icon_label.strip() else ""
        if overlay.lower() in {"-imageoverlaylabel", "imageoverlaylabel"}:
            overlay = ""

        return {
            "full_path": full_path,
            "label": overlay,
            "name": label.strip() if label else "",
            "annotation": ann,
            "icon_label": icon_label,
            "icon": icon,
            "icon_candidates": icon_candidates,
            "command": command,
            "sourceType": src,
            "doubleClickCommand": dbl_cmd,
            "doubleClickSourceType": src,
            "pie_commands": [],
        }

    # ------------------------------------------------------------------
    # Keyboard navigation
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Tab key → toggle the Free Stuff view, in-place in this same grid
    # ------------------------------------------------------------------
    # Qt normally intercepts Key_Tab for focus traversal inside
    # QWidget.event() *before* it ever reaches keyPressEvent(), so the
    # only reliable place to claim it is here.
    def event(self, event):
        if (event.type() == QtCore.QEvent.KeyPress
                and event.key() == QtCore.Qt.Key_Tab
                and not event.isAutoRepeat()):
            focused = QtWidgets.QApplication.focusWidget()
            if not isinstance(focused, (
                QtWidgets.QLineEdit, QtWidgets.QTextEdit,
                QtWidgets.QPlainTextEdit, QtWidgets.QAbstractSpinBox,
            )):
                self._toggle_free_stuff_view()
                return True
        return super(PhoenixPanel, self).event(event)

    def _toggle_free_stuff_view(self):
        if getattr(self, "_free_stuff_active", False):
            self._exit_free_stuff_view()
        else:
            self._enter_free_stuff_view()

    def _enter_free_stuff_view(self):
        """Swap this panel's own grid over to the Free Stuff catalog —
        same window, same button grid, same click-to-run behaviour as
        any other button (rebuild_grid() doesn't know or care where
        buttons_data came from). Nothing here is written to disk:
        save_tab_config() no-ops for the duration (see its own guard)."""
        try:
            from .free_stuff import get_cached_buttons_data, request_buttons_data
        except Exception as e:
            cmds.warning("ModPanel Free Stuff: {}".format(e))
            return

        self._free_stuff_active = True
        self._free_stuff_saved_buttons = self.buttons_data
        cached = get_cached_buttons_data()
        self.buttons_data = cached if cached is not None else []
        self._grid_dirty = True

        # The catalog can be a lot of buttons to hunt through by eye —
        # keep the search bar up the whole time this view is active,
        # regardless of the search_always_on setting. Remember whatever
        # it was so a plain Tab-toggle exit puts it back exactly as it
        # was, rather than always collapsing it.
        if hasattr(self, "_search_bar"):
            self._free_stuff_prior_search_visible = self._search_bar.isVisible()
            self._search_bar.setVisible(True)

        if self._ui_built:
            self.rebuild_grid()
            self._grid_dirty = False
            self._update_title_tab_hint(); self._rebuild_title_tooltip()
            self._resize_to_content()
            self.setFocus()

        # Refresh from the repo in the background (cheap listing calls;
        # actual downloads only happen for files that are missing or
        # actually changed) and swap the grid again once that lands.
        request_buttons_data(self._on_free_stuff_buttons_ready)

    def _on_free_stuff_buttons_ready(self, buttons_data):
        if not getattr(self, "_free_stuff_active", False):
            return   # user already tabbed back out — ignore this stale callback
        self.buttons_data = buttons_data
        self._grid_dirty = True
        if self._ui_built:
            self.rebuild_grid()
            self._grid_dirty = False
            self._resize_to_content()

    def _exit_free_stuff_view_state_only(self):
        """Clear Free Stuff flags/search-bar state without touching
        buttons_data or doing any rebuild — callers decide what
        buttons_data becomes next and whether a rebuild is warranted."""
        self._free_stuff_active = False
        self._free_stuff_saved_buttons = None
        if hasattr(self, "_search_bar"):
            prior = getattr(self, "_free_stuff_prior_search_visible", False)
            self._free_stuff_prior_search_visible = None
            if not self.search_always_on:
                self._search_bar.setVisible(bool(prior))

    def _exit_free_stuff_view(self, rebuild=True):
        saved = getattr(self, "_free_stuff_saved_buttons", None) or []
        self._exit_free_stuff_view_state_only()
        self.buttons_data = saved
        self._grid_dirty = True
        if rebuild and self._ui_built:
            self.rebuild_grid()
            self._grid_dirty = False
            self._update_title_tab_hint(); self._rebuild_title_tooltip()
            self._resize_to_content()
            self.setFocus()

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return

        # If search bar is visible, Escape hides it; all other keys flow to it normally
        if hasattr(self, "_search_bar") and self._search_bar.isVisible():
            if event.key() == QtCore.Qt.Key_Escape:
                self._hide_search()
                return
            super(PhoenixPanel, self).keyPressEvent(event)
            return

        # Guard: don't intercept typing in text-entry children
        focused = QtWidgets.QApplication.focusWidget()
        if isinstance(focused, (
            QtWidgets.QLineEdit, QtWidgets.QTextEdit,
            QtWidgets.QPlainTextEdit, QtWidgets.QAbstractSpinBox,
        )):
            super(PhoenixPanel, self).keyPressEvent(event)
            return

        # X: show search bar (when not always-on; that keeps it visible regardless)
        if event.key() == QtCore.Qt.Key_X:
            if not getattr(self, "search_always_on", False):
                self._show_search()
            return

        tab_index = self._SHORTCUT_MAP.get(event.key())
        if tab_index is not None:
            self._switch_and_resize(tab_index)
            return

        super(PhoenixPanel, self).keyPressEvent(event)

    # ------------------------------------------------------------------
    # Auto-sizing helpers
    # ------------------------------------------------------------------
    def _compute_ideal_size(self):
        """Return (width, height) that snugly fits the current button grid."""
        ps       = self.panel_scale
        base     = 64
        side     = int(base * self.button_scale * ps)
        look = self.export_look_settings()
        btn_cell = side + int(2 * look["button_padding"] * ps)
        pad      = int(self.padding * ps)
        cols     = max(1, self.cols)

        real_btns = self.buttons_data
        total     = len(real_btns)

        if total == 0:
            return int(260 * ps), int(160 * ps)

        rows_needed = (total + cols - 1) // cols

        # Grid content; grid_layout has contentsMargins(8, 8, 8, 8)
        grid_w = cols * btn_cell + max(0, cols - 1) * pad + int(16 * ps)
        grid_h = rows_needed * btn_cell + max(0, rows_needed - 1) * pad + int(16 * ps)

        # Minimum width: title row must fit the slider-controlled number of hot buttons.
        hbs = self.hot_button_icon_scale
        gap = int(getattr(self, "quick_button_gap", 4) * ps)
        vis_count = self._clamp_quick_button_count(
            getattr(self, "quick_button_count", 0)
        )
        hot_btn_side = int(24 * ps * hbs)
        btn_frame_w = (vis_count * hot_btn_side + max(0, vis_count - 1) * gap
                       + int(8 * ps)) if vis_count else 0
        # Always reserve space for pin/add/settings + title label + panel margins
        TITLE_ROW_MIN = btn_frame_w + int((3 * 26 + 4 * 4 + 70 + 20) * ps)
        W_OVERHEAD = int(44 * ps)
        H_OVERHEAD = int(72 * ps)
        # Extra height when the hot-button row grows taller than its base
        # size (26px at panel_scale) — otherwise a big hot_button_icon_scale
        # would make the row taller than what H_OVERHEAD already assumes,
        # clipping/overlapping the button grid below it.
        H_OVERHEAD += max(0, int(26 * ps * hbs) - int(26 * ps))

        # Optional bars — use isHidden() (widget's own state) not isVisible()
        # because isVisible() returns False when the parent window is hidden,
        # which is exactly the case when show_at_cursor computes the size.
        if getattr(self, "_search_bar", None) and not self._search_bar.isHidden():
            H_OVERHEAD += int(34 * ps)   # 26px bar + 8px spacing
        if getattr(self, "_recent_frame", None) and not self._recent_frame.isHidden():
            H_OVERHEAD += int(38 * ps)   # 30px frame + 8px spacing

        return (max(TITLE_ROW_MIN, grid_w + W_OVERHEAD),
                max(int(120 * ps), grid_h + H_OVERHEAD))

    def _switch_and_resize(self, tab_index):
        """Switch to *tab_index* and auto-resize the panel to fit its content.

        Used by keyPressEvent. Unlike switch_tab() it also recalculates the
        panel dimensions, repositions if needed, and reclaims keyboard focus
        so subsequent shortcuts keep working.
        """
        if tab_index < 0 or tab_index >= _TOTAL_TABS:
            return

        # Clear any active search before switching (avoid stale filtered view)
        if getattr(self, "_search_was_active", False):
            if hasattr(self, "_search_bar"):
                self._search_bar.blockSignals(True)
                self._search_bar.clear()
                self._search_bar.blockSignals(False)
            self._search_was_active = False

        # Leaving the Free Stuff view via a real tab shortcut. current_tab
        # was never changed while Free Stuff was active, so pressing the
        # shortcut for that same tab must still force a reload — the
        # ordinary "tab_index != self.current_tab" check below would
        # otherwise treat it as a no-op and leave the catalog on screen.
        # Never save first: buttons_data right now is still the Free
        # Stuff catalog, not real data for self.current_tab.
        leaving_free_stuff = getattr(self, "_free_stuff_active", False)
        if leaving_free_stuff:
            self._exit_free_stuff_view_state_only()
            self.current_tab = tab_index
            self.load_tab_config(tab_index)
            self._grid_dirty = True
        elif tab_index != self.current_tab:
            self.save_tab_config(self.current_tab)
            self.current_tab = tab_index
            self.load_tab_config(tab_index)
            self._grid_dirty = True

        if self._ui_built:
            if self._grid_dirty:
                self.rebuild_grid()
                self._grid_dirty = False
            self.update_quick_buttons()
            self._update_tab_indicators()
            self._update_title_tab_hint(); self._rebuild_title_tooltip()

        # Resize to fit the new panel's content
        new_w, new_h = self._compute_ideal_size()
        self.panel_width  = new_w
        self.panel_height = new_h

        # Clamp to screen so the panel stays fully on-screen
        pos    = QtGui.QCursor.pos()
        app    = QtWidgets.QApplication.instance()
        screen = app.screenAt(pos) if hasattr(app, "screenAt") else app.primaryScreen()
        rect   = screen.availableGeometry()
        m      = self.MARGIN
        x, y   = self.x(), self.y()

        if x + new_w + m > rect.right():   x = rect.right()  - new_w - m
        if y + new_h + m > rect.bottom():  y = rect.bottom() - new_h - m
        if x < rect.left() + m:            x = rect.left()   + m
        if y < rect.top()  + m:            y = rect.top()    + m

        self.setGeometry(x, y, new_w, new_h)
        # Reclaim focus so the next key press still hits keyPressEvent
        self.setFocus()
        self.save_global_state()

    # ------------------------------------------------------------------
    # Pin mode
    # ------------------------------------------------------------------
    def _toggle_pin(self):
        """Toggle pin mode — pinned panel ignores outside-click dismissal.
        Both modes now use the same window flags; previously the unpinned
        case used Qt.Popup for its automatic outside-click auto-close, but
        Qt.Popup tracks its own internal mouse-grab state in the C++ layer,
        and the pie system's hold-to-open handling deliberately consumes
        raw mouse press/release events on buttons that have pie commands
        configured (even for an ordinary short click) — which can desync
        that internal tracking and leave the popup unable to auto-close for
        the rest of the session. The manual outside-click check in
        eventFilter() (frameGeometry/widgetAt based) doesn't depend on any
        of that, so it's now the sole dismiss mechanism in both modes."""
        self._pinned = not self._pinned
        if hasattr(self, "_pin_btn"):
            self._pin_btn.setChecked(self._pinned)
        flags = (QtCore.Qt.Tool |
                 QtCore.Qt.FramelessWindowHint)
        self.setWindowFlags(flags)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _refresh_pin_icon(self):
        """(Re)paint the pin glyph at the button's current size/state. Safe
        to call anytime — construction, scale changes, or toggling."""
        if not hasattr(self, "_pin_btn"):
            return
        box = self._pin_btn.width() or int(26 * self.panel_scale)
        color = _theme.col("#5ab4ff" if self._pin_btn.isChecked() else "#505878")
        try:
            self._pin_btn.setIcon(_render_glyph_icon("◎", box, color))
            self._pin_btn.setIconSize(QtCore.QSize(box, box))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Search bar
    # ------------------------------------------------------------------
    def _show_search(self):
        if not hasattr(self, "_search_bar"):
            return
        self._search_bar.setVisible(True)
        self._search_bar.setFocus()
        self._search_bar.selectAll()
        if self._ui_built:
            self._resize_to_content()   # expand panel to accommodate search bar

    def _hide_search(self):
        """Hide the search bar and shrink the panel back to fit."""
        if not hasattr(self, "_search_bar"):
            return
        # Clearing text fires textChanged → _apply_search_filter("") → rebuild_grid()
        self._search_bar.clear()
        self._search_bar.setVisible(self.search_always_on)
        self.setFocus()
        if self._ui_built:
            self._resize_to_content()   # shrink panel back

    def _apply_search_filter(self, text):
        """Search: show only matching buttons at the top of the grid.

        Clears and rebuilds the grid view — non-matching buttons are hidden
        entirely. When text is empty the original layout is restored.
        """
        text = text.strip().lower()

        if not text:
            if getattr(self, "_search_was_active", False):
                self._search_was_active = False
                self.rebuild_grid()
            return

        self._search_was_active = True

        # Collect matching data indices
        matching = [
            i for i, info in enumerate(self.buttons_data)
            if (text in (info.get("label", "") or "").lower()
                or text in (info.get("annotation", "") or "").lower())
        ]

        # Clear grid and rebuild with only matched items at the top
        self.clear_grid()
        if not matching:
            return

        base      = 64
        side      = int(base * self.button_scale * self.panel_scale)
        icon_size = int(side * 0.82)
        pad       = int(self.padding * self.panel_scale)
        cols      = self.cols
        total     = len(matching)

        all_btns = []
        for i in matching:
            info    = self.buttons_data[i]
            overlay = info.get("label", "") or ""
            ann     = info.get("annotation", "") or ""
            icon_name = info.get("icon", "")
            icon    = self._resolve_info_icon(info, icon_size)
            btn = self._PhoenixButtonWidget(i, overlay, icon, ann,
                                            parent=self.grid_container)
            btn.set_theme(self.export_look_settings())
            btn.set_sizes(side, icon_size)
            btn.triggeredWithIndex.connect(self._on_button_triggered)
            btn.middleClickTriggered.connect(self._on_button_middle)
            btn.requestDelete.connect(self._on_button_delete)
            btn.requestEditLabel.connect(self._on_request_edit_label)
            btn.requestChangeIcon.connect(self._on_request_change_icon)
            btn.requestEditPie.connect(self._on_request_edit_pie)
            btn.requestAddToPie.connect(self._on_request_add_to_pie)
            btn.requestToggleCloseBehavior.connect(self._on_toggle_button_close_behavior)
            btn.pieCommandTriggered.connect(self._on_pie_command_triggered)
            btn.configure_pie(
                pie_provider=lambda idx: (
                    self.buttons_data[idx].get("pie_commands", [])
                    if idx < len(self.buttons_data) else []),
                angle_provider=lambda idx: (
                    self.buttons_data[idx].get("pie_start_angle")
                    if idx < len(self.buttons_data) else None),
                icon_resolver=self._resolve_pie_icon,
                main_icon_name=icon_name,
            )
            # Reposition is disabled while search is active (indices are virtual)
            all_btns.append(btn)
            self.button_widgets.append(btn)

        num_rows = (total + cols - 1) // cols
        for r in range(num_rows):
            row_btns  = all_btns[r * cols : (r + 1) * cols]
            is_partial = (r == num_rows - 1) and (total % cols != 0)
            align = (self.grid_row_alignment if is_partial
                     else self.grid_full_row_alignment)
            row_w = QtWidgets.QWidget()
            _theme.set_qss(row_w, "background: transparent;")
            rl = QtWidgets.QHBoxLayout(row_w)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(pad)
            self._apply_row_align(rl, row_btns, align)
            if r > 0:
                self.grid_layout.addSpacing(pad)
            self.grid_layout.addWidget(row_w)

    # ------------------------------------------------------------------
    # Separator
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Recent commands row
    # ------------------------------------------------------------------
    def _add_to_recent(self, info):
        """Track a button invocation (max 5, deduplicated, global)."""
        entry = {
            "label":      info.get("label", ""),
            "annotation": info.get("annotation", ""),
            "icon":       info.get("icon", ""),
            "command":    info.get("command", ""),
            "sourceType": info.get("sourceType", "mel"),
            "invert_close_on_click": bool(info.get("invert_close_on_click", False)),
        }
        # Remove existing duplicate then insert at front
        self.recent_commands = [
            r for r in self.recent_commands
            if not (r.get("command") == entry["command"]
                    and r.get("label") == entry["label"])
        ]
        self.recent_commands.insert(0, entry)
        self.recent_commands = self.recent_commands[:5]
        if self._ui_built:
            self._update_recent_row()
        self.save_global_state()

    def _update_recent_row(self):
        """Rebuild the recent commands mini-button strip from self.recent_commands."""
        if not (hasattr(self, "_recent_frame") and hasattr(self, "_recent_layout")):
            return

        # Clear existing mini buttons
        while self._recent_layout.count():
            item = self._recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        visible = self.recent_commands_enabled and bool(self.recent_commands)
        self._recent_frame.setVisible(visible)
        if self._ui_built and self.isVisible():
            self._resize_to_content()   # expand/collapse panel to fit
        if not visible:
            return

        side = max(18, int(64 * self.button_scale * self.panel_scale * 0.52))

        for cmd_info in self.recent_commands[:5]:
            icon  = self._sized_icon(cmd_info.get("icon", ""), side)
            label = cmd_info.get("label", "")
            tip   = cmd_info.get("annotation", "") or label or "Recent"
            cmd   = cmd_info.get("command", "")
            src   = cmd_info.get("sourceType", "mel")

            mini = QtWidgets.QToolButton()
            mini.setIcon(icon)
            mini.setToolTip(tip)
            mini.setFixedSize(side + 4, side + 4)
            mini.setIconSize(QtCore.QSize(side, side))
            look = self.export_look_settings()
            _theme.set_qss(mini, """
            QToolButton {{
                background: {button}; border-radius: {radius}px;
                padding: {padding}px; color: {icon};
            }}
            QToolButton:hover {{ background: {hover}; }}
            QToolButton:pressed {{ background: {pressed}; }}
            """.format(button=look["button"],
                       radius=max(0, min(12, int(look["corner_radius"] * 0.45))),
                       padding=max(0, int(look["button_padding"] * 0.35)),
                       icon=look["icon"], hover=look["button_hover"],
                       pressed=look["button_pressed"]))
            if label:
                ol = QtWidgets.QLabel(label, mini)
                ol.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
                _theme.set_qss(ol, """
                QLabel {{
                    background: rgba(0,0,0,160);
                    color: {text}; font-size: 6px;
                    border-bottom-left-radius: 4px;
                    border-bottom-right-radius: 4px;
                }}
                """.format(text=look["text"]))
                ol.setAlignment(QtCore.Qt.AlignCenter)
                ol.setGeometry(0, mini.height() - 10, mini.width(), 10)
            mini.clicked.connect(
                lambda _=False, c=cmd, s=src, info=cmd_info:
                    self._run_command(c, s, button_info=info)
            )
            self._recent_layout.addWidget(mini)

        self._recent_layout.addStretch(1)

    def _run_command(self, cmd, src, button_info=None):
        """Run a command string (shared by recent row and future callers)."""
        if not cmd:
            return
        self._prepare_command_execution(button_info)
        try:
            if src == "python":
                import __main__
                exec(cmd, __main__.__dict__)
            else:
                mel.eval(cmd)
        except Exception as e:
            cmds.warning("ModPanel: {}".format(e))
        finally:
            QtCore.QTimer.singleShot(300, self._rearm_dismiss)

    def _resize_to_content(self):
        """Immediately resize the panel to exactly fit all currently visible sections.

        Called after toggling the search bar or recent commands row so the
        panel expands/contracts smoothly without any wasted space.
        """
        if not self.isVisible():
            return
        new_w, new_h = self._compute_ideal_size()
        pos    = self.pos()
        app    = QtWidgets.QApplication.instance()
        screen = app.screenAt(pos) if hasattr(app, "screenAt") else app.primaryScreen()
        rect   = screen.availableGeometry()
        m      = self.MARGIN
        x, y   = self.x(), self.y()
        if x + new_w + m > rect.right():   x = rect.right()  - new_w - m
        if y + new_h + m > rect.bottom():  y = rect.bottom() - new_h - m
        if x < rect.left() + m:            x = rect.left()   + m
        if y < rect.top()  + m:            y = rect.top()    + m
        self.setGeometry(x, y, new_w, new_h)

    # ------------------------------------------------------------------
    # Show at cursor
    # ------------------------------------------------------------------
    def show_at_cursor(self, desired_tab=None):
        # Defensive reset: nothing from a previous open/dialog interaction
        # should ever leave the panel permanently unable to dismiss on an
        # outside click. Both of these flags are only ever meant to be true
        # for the duration of a single, short-lived operation (running a
        # command, or a modal dialog being open) — if either is still true
        # by the time the panel is being (re)shown, something didn't reset
        # it properly last time, so force it back to a clean state now.
        self._ignore_close = False
        if self._reposition_mode:
            self._exit_reposition_mode()

        if desired_tab is None:
            desired_tab = _detect_desired_tab()

        # Tab switch handled by launcher (destroys+recreates instance).
        # If somehow we still need to switch, do it silently before any paint.
        if desired_tab != self.current_tab:
            self.save_tab_config(self.current_tab)
            self.current_tab = desired_tab
            self.load_tab_config(desired_tab)
            self._grid_dirty = True

        self.setUpdatesEnabled(False)
        self._ensure_ui_built()

        # Always start with search collapsed — never persist the expanded state
        if hasattr(self, "_search_bar") and not self.search_always_on:
            if self._search_bar.isVisible() or self._search_was_active:
                self._search_bar.blockSignals(True)
                self._search_bar.clear()
                self._search_bar.blockSignals(False)
                self._search_bar.setVisible(False)
                self._search_was_active = False

        if self._grid_dirty:
            self.rebuild_grid()
            self._grid_dirty = False

        self.update_quick_buttons()
        self._rebuild_quick_buttons_layout()
        self._update_tab_indicators()
        self._update_title_tab_hint(); self._rebuild_title_tooltip()
        # Sync the recent commands strip before computing size
        # (needed for new instances where the strip hasn't been shown yet)
        if self._ui_built:
            self._update_recent_row()

        # Calculate position and size
        pos  = QtGui.QCursor.pos()
        app  = QtWidgets.QApplication.instance()
        screen = app.screenAt(pos) if hasattr(app, "screenAt") else app.primaryScreen()
        rect = screen.availableGeometry()
        # Size derived from content — auto-fits buttons with clean padding
        w, h = self._compute_ideal_size()
        x, y = pos.x(), pos.y()
        m    = self.MARGIN

        if x + w + m > rect.right():  x = rect.right()  - w - m
        if y + h + m > rect.bottom(): y = rect.bottom() - h - m
        if x < rect.left()  + m:      x = rect.left()   + m
        if y < rect.top()   + m:      y = rect.top()    + m

        # Place window at correct position BEFORE re-enabling updates
        # so no intermediate paint happens at 0,0
        self.setGeometry(x, y, w, h)
        self.setUpdatesEnabled(True)
        # Both pinned and unpinned use the same flags now. Qt.Popup used to
        # be used here for its automatic outside-click auto-close, but its
        # internal mouse-grab tracking (in Qt's C++ layer) gets desynced by
        # the pie system's hold-to-open handling, which deliberately
        # consumes raw mouse press/release events on any button that has
        # pie commands configured — even for an ordinary short click. Once
        # desynced, Qt.Popup can stop auto-closing for the rest of the
        # session. The manual outside-click check in eventFilter() doesn't
        # depend on any of that internal state, so it's the sole dismiss
        # mechanism now (still gated on `not self._pinned` there).
        flags = (QtCore.Qt.Tool |
                 QtCore.Qt.FramelessWindowHint)
        self.setWindowFlags(flags)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()   # ensure keyboard shortcuts fire immediately on open

    # ------------------------------------------------------------------
    # Close / cleanup
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event):
        # Maya's own shelf-button MMB-drag turns out to be a genuine Qt
        # QDrag (the "forbidden" cursor Qt shows when nothing accepts a
        # drag is what tipped this off) — not the native-control-only path
        # _setup_shelf_drop_zone was built for. Handling it directly here
        # is simpler and more reliable than that bridge.
        if self._pinned and event.mimeData() is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._pinned:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not self._pinned:
            event.ignore()
            return

        try:
            src_widget = event.source()
        except Exception:
            src_widget = None
        md = event.mimeData()

        try:
            local_pos = event.position().toPoint()
        except AttributeError:
            local_pos = event.pos()
        target = self._find_button_at_pos(local_pos)

        event.acceptProposedAction()

        # Defer the actual Maya queries (cmds.shelfButton(...)) and whatever
        # follows (the confirmation dialog, or the import itself) to the
        # next idle tick instead of running them synchronously right here.
        # Maya's own shelf drag-and-drop teardown can still be unwinding at
        # the exact moment dropEvent fires, and doing Maya command queries
        # or opening a modal dialog while that's in progress is what was
        # causing a noticeable (~1s) stall before anything appeared.
        QtCore.QTimer.singleShot(
            0, lambda: self._handle_shelf_drop(src_widget, md, target))

    def _handle_shelf_drop(self, src_widget, mime_data, target):
        info = self._shelf_button_info_from_source(src_widget, mime_data)
        if info is None:
            return
        if target is not None:
            self._prompt_shelf_drop_target(info, target)
        else:
            self._import_shelf_button_as_new(info)

    def _find_button_at_pos(self, local_pos):
        """Returns ("hot", index) or ("panel", index) if `local_pos` (panel-
        local coordinates) lands on an existing button, else None."""
        w = self.childAt(local_pos)
        if w is None:
            return None
        for i, qb in enumerate(getattr(self, "quick_buttons", [])):
            if qb is w or qb.isAncestorOf(w):
                return ("hot", i)
        for i, bw in enumerate(getattr(self, "button_widgets", [])):
            tb = getattr(bw, "tool_btn", None)
            if tb is not None and (tb is w or tb.isAncestorOf(w)):
                return ("panel", i)
        return None

    def _import_shelf_button_as_new(self, info):
        self.buttons_data.append(info)
        self._grid_dirty = True
        self.rebuild_grid()
        self.save_tab_config(self.current_tab)
        try:
            cmds.inViewMessage(
                amg="Imported <hl>{}</hl> into this panel".format(
                    info.get("label") or info.get("name") or "shelf button"),
                pos="topCenter", fade=True)
        except Exception:
            pass

    def _prompt_shelf_drop_target(self, info, target):
        """A shelf icon was dropped directly onto an existing button —
        ask whether it should join that button's pie menu or just be
        imported as its own new standalone button."""
        kind, idx = target
        if kind == "hot":
            if not (0 <= idx < len(self.custom_buttons)):
                self._import_shelf_button_as_new(info)
                return
            name = (self.custom_buttons[idx].get("name") or "").strip() or "Hot Button {}".format(idx + 1)
            target_label = "Hot Button {}: {}".format(idx + 1, name)
        else:
            if not (0 <= idx < len(self.buttons_data)):
                self._import_shelf_button_as_new(info)
                return
            b = self.buttons_data[idx]
            name = (b.get("label") or b.get("name") or "").strip() or "Button {}".format(idx + 1)
            target_label = "Panel Button: {}".format(name)

        shelf_name = (info.get("label") or info.get("name") or "").strip() or "This shelf button"

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Add Shelf Button")
        dlg.resize(360, 190)
        _theme.set_qss(dlg, "background:#1b1e29; color:#dfe3ff;")
        lay = QtWidgets.QVBoxLayout(dlg)

        msg = QtWidgets.QLabel(
            "\u201c{}\u201d was dropped on {}. Add it to that button's pie "
            "menu, or import it as its own new button?".format(shelf_name, target_label))
        msg.setWordWrap(True)
        _theme.set_qss(msg, "color:#dfe3ff; font-size:11px;")
        lay.addWidget(msg)
        lay.addStretch(1)

        def _styled_btn(text):
            b = QtWidgets.QPushButton(text)
            b.setFixedHeight(30)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            _theme.set_qss(b, """
            QPushButton {
                background:#252a39; color:#c8d2ff; border:1px solid #3a4060;
                border-radius:6px; font-size:11px;
            }
            QPushButton:hover { background:#2e3448; }
            """)
            return b

        add_pie_btn = _styled_btn("Add to This Button's Pie Menu")
        add_new_btn = _styled_btn("Add as New Button")
        cancel_btn  = _styled_btn("Cancel")
        for b in (add_pie_btn, add_new_btn, cancel_btn):
            lay.addWidget(b)

        choice = {"value": None}

        def _pick(v):
            choice["value"] = v
            dlg.accept()

        add_pie_btn.clicked.connect(lambda: _pick("pie"))
        add_new_btn.clicked.connect(lambda: _pick("new"))
        cancel_btn.clicked.connect(dlg.reject)

        self._ignore_close = True
        try:
            dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        finally:
            self._ignore_close = False

        # Deferred so the dialog's own close/teardown fully finishes before
        # the heavier rebuild work (grid rebuild + icon resolution + disk
        # save) starts, rather than running back-to-back with it.
        if choice["value"] == "pie":
            QtCore.QTimer.singleShot(0, lambda: self._add_shelf_info_to_pie(info, target))
        elif choice["value"] == "new":
            QtCore.QTimer.singleShot(0, lambda: self._import_shelf_button_as_new(info))
        # else Cancel — do nothing at all

    def _add_shelf_info_to_pie(self, info, target):
        pie_cmd = {
            "name":    (info.get("label") or info.get("name") or "").strip(),
            "tooltip": info.get("annotation", ""),
            "type":    (info.get("sourceType", "mel") or "mel").lower(),
            "code":    info.get("command", ""),
            "icon":    info.get("icon", ""),
        }
        if not pie_cmd["code"].strip():
            cmds.warning("ModPanel: this shelf button has no command to add.")
            return

        kind, idx = target
        if kind == "hot":
            if not (0 <= idx < len(self.custom_buttons)):
                return
            pies = _sanitize_pie_commands(self.custom_buttons[idx].get("pie_commands", []))
        else:
            if not (0 <= idx < len(self.buttons_data)):
                return
            pies = _sanitize_pie_commands(self.buttons_data[idx].get("pie_commands", []))

        if len(pies) >= MAX_PIE_COMMANDS:
            cmds.warning("ModPanel: this button already contains the "
                         "maximum of six pie commands.")
            return
        for existing in pies:
            if (existing.get("code", "") == pie_cmd["code"] and
                    existing.get("type", "") == pie_cmd["type"]):
                cmds.warning("ModPanel: that command is already in this "
                             "button's pie.")
                return
        pies.append(pie_cmd)

        if kind == "hot":
            self.custom_buttons[idx]["pie_commands"] = pies
            self.save_global_state()
            self.update_quick_buttons()
            try:
                cmds.inViewMessage(amg="Added to <hl>Hot Button {}</hl> pie".format(idx + 1),
                                    pos="topCenter", fade=True)
            except Exception:
                pass
        else:
            self.buttons_data[idx]["pie_commands"] = pies
            self.save_tab_config(self.current_tab)
            if idx < len(self.button_widgets):
                self.button_widgets[idx].refresh_tooltip()
            try:
                cmds.inViewMessage(amg="Added to <hl>Panel Button</hl> pie",
                                    pos="topCenter", fade=True)
            except Exception:
                pass

    def _shelf_button_info_from_source(self, src_widget, mime_data):
        """Resolve a dropped Maya shelf button to the same info dict shape
        ShelfPickerDialog.selected_buttons() produces.

        Preferred path: `src_widget` is the actual QWidget that started
        the drag (from event.source(), captured synchronously in
        dropEvent before this runs) — reliable and unambiguous, since
        Maya's shelf lives in the same Qt application/process as this
        panel. Once we have that widget, MQtUtil.fullName() maps it
        straight back to its Maya control name, which we already know how
        to query directly.
        """
        full_path = None
        fast_tip = None
        if src_widget is not None:
            try:
                fast_tip = src_widget.toolTip()
            except Exception:
                fast_tip = None
            try:
                import maya.OpenMayaUI as omui
                try:
                    import shiboken6 as shiboken
                except ImportError:
                    import shiboken2 as shiboken
                ptr = shiboken.getCppPointer(src_widget)
                if isinstance(ptr, (tuple, list)):
                    ptr = ptr[0]
                full_path = omui.MQtUtil.fullName(int(ptr))
            except Exception:
                full_path = None

        if full_path and cmds.shelfButton(full_path, exists=True):
            return self._shelf_button_info_from_control(full_path, fast_annotation=fast_tip)

        # Fallback: some Maya versions/platforms may put something usable
        # directly in the mime data instead (varies enough that we can't
        # rely on one specific format — try text and see if it happens to
        # name a live shelfButton control).
        if mime_data is None:
            return None
        candidates = []
        if mime_data.hasText():
            candidates.append(mime_data.text())
        for fmt in mime_data.formats():
            try:
                candidates.append(bytes(mime_data.data(fmt)).decode("utf-8", "ignore"))
            except Exception:
                continue
        for text in candidates:
            candidate = (text or "").strip()
            if candidate and cmds.shelfButton(candidate, exists=True):
                return self._shelf_button_info_from_control(candidate)
        return None

    def resizeEvent(self, event):
        super(PhoenixPanel, self).resizeEvent(event)
        drop_widget = getattr(self, "_shelf_drop_widget", None)
        if drop_widget is not None:
            try:
                drop_widget.setGeometry(0, 0, self.width(), self.height())
            except Exception:
                pass

    def hideEvent(self, event):
        # hide() (outside-click dismiss, Escape, etc.) doesn't route through
        # closeEvent, but a held pie or an in-progress "Add to Another
        # Button's Pie" pick must never survive the panel disappearing.
        self._cancel_all_active_pies()
        # Never let the panel come back showing the Free Stuff catalog
        # instead of whatever real tab was actually active — this is the
        # same path launcher.py's open_phoenix_panel() uses to hide the
        # panel right before (re)showing it.
        if getattr(self, "_free_stuff_active", False):
            self._exit_free_stuff_view(rebuild=False)
        super(PhoenixPanel, self).hideEvent(event)

    def closeEvent(self, event):
        if getattr(self, "_free_stuff_active", False):
            self._exit_free_stuff_view(rebuild=False)
        self._cancel_all_active_pies()
        self._exit_reposition_mode()
        self.save_tab_config(self.current_tab)
        self.save_global_state()
        self._stop_workspace_polling()

        win_name = getattr(self, "_shelf_drop_window", None)
        if win_name:
            try:
                if cmds.window(win_name, exists=True):
                    cmds.deleteUI(win_name)
            except Exception:
                pass
        self._shelf_drop_widget = None
        self._shelf_drop_window = None

        for obj in self._event_filters_installed:
            try:
                obj.removeEventFilter(self)
            except Exception:
                pass
        self._event_filters_installed.clear()

        for btn in self.button_widgets:
            try:
                btn.cleanup()
            except Exception:
                pass

        for btn in self.quick_buttons:
            try:
                btn.clicked.disconnect()
            except Exception:
                pass

        super(PhoenixPanel, self).closeEvent(event)