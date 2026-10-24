# -*- coding: utf-8 -*-
"""UI style presets for ModPanel.

Every stylesheet in the plugin is authored against the original ("Classic")
palette. Instead of duplicating ~200 stylesheets, widgets are styled through
``set_qss`` which remembers the authored source and translates it into the
active style: classic colours are remapped and corner radii softened. Switching
styles re-translates every live widget from its stored source, so a preset
change applies instantly without rebuilding any window.

Styles:
  "modpanel" - default. Black surfaces, thin neutral outlines, cyan-blue
               accent (#46b6ff) and small corner radii.
  "classic"  - the original PhoenixPanel navy palette, untouched.
"""

from __future__ import annotations

import re

try:
    from PySide6 import QtWidgets, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtGui

APP_NAME = "ModPanel"

DEFAULT_STYLE = "modpanel"
STYLE_LABELS = {
    "modpanel": "ModPanel (Dark)",
    "classic":  "Classic (PhoenixPanel)",
}
STYLE_ORDER = ("modpanel", "classic")

# Panel Look colours/shape each style applies to the Look settings when
# selected. Title, scale and spacing are user layout choices and untouched.
LOOK_PRESETS = {
    "modpanel": {
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
        "corner_radius":    6,
    },
    "classic": {
        "panel_background": "#151820",
        "panel_border":     "#303645",
        "title_bar":        "#151820",
        "button":           "#202432",
        "button_hover":     "#2a3042",
        "button_pressed":   "#161a24",
        "button_selected":  "#1e3050",
        "text":             "#f5f7ff",
        "icon":             "#c8d2ff",
        "accent":           "#4a7bb8",
        "corner_radius":    12,
    },
}
LOOK_PRESET_KEYS = tuple(LOOK_PRESETS["classic"].keys())

# Classic colour -> ModPanel colour. Hues outside the blue/navy family
# (status greens/reds, tab oranges, warnings) are intentionally absent and
# pass through unchanged.
_MODPANEL_COLOURS = {
    # deepest backgrounds
    "#070c18": "#030b10", "#0a0c12": "#050505", "#0d0f18": "#000000",
    "#0e1016": "#000000", "#0e1018": "#050505", "#10131a": "#050505",
    "#101320": "#050505", "#111420": "#080808", "#14161f": "#050505",
    "#151820": "#000000", "#151824": "#080808", "#161a24": "#050505",
    "#171b28": "#080808",
    # raised surfaces / buttons
    "#1b1e29": "#0c0c0c", "#1b1f2d": "#0c0c0c", "#1c2030": "#0a0a0a",
    "#202432": "#0c0c0c", "#212121": "#0a0a0a", "#232838": "#111111",
    "#252a39": "#0c0c0c",
    # hover surfaces
    "#242a3d": "#141414", "#28304a": "#141414", "#2a3042": "#141414",
    "#2e3448": "#141414", "#2f3547": "#141414", "#32384c": "#181818",
    "#2e2e2e": "#161616", "#3a4055": "#1c1c1c", "#373737": "#1f1f1f",
    # outlines
    "#262b3d": "#262626", "#2a3050": "#303030", "#2c3348": "#303030",
    "#303645": "#2b2b2b", "#323852": "#383838", "#33395a": "#383838",
    "#3a3a3a": "#333333", "#3a4060": "#484848",
    # neutral/muted text
    "#50586b": "#3c3c3c", "#505878": "#6a6a6a", "#5c6688": "#5a5a5a",
    "#7d84a3": "#898989", "#8894c0": "#9a9a9a", "#adb4d1": "#a5a5a5",
    "#c8d2ff": "#d0d0d0", "#d6daf5": "#d6d6d6", "#dfe3ff": "#e6e6e6",
    "#f5f6fc": "#f2f2f2", "#f5f7ff": "#f2f2f2",
    # selection / accent backgrounds
    "#0d1a30": "#030b10", "#0f2440": "#081d2b", "#1a2c47": "#071018",
    "#1e3050": "#071018", "#2a3a5a": "#071018", "#1f3f66": "#081d2b",
    "#1c4278": "#0a2a40", "#1e4a86": "#0c3350", "#2f649c": "#1f6a99",
    # accents
    "#2f8fef": "#46b6ff", "#3d6bb0": "#2a8fd0", "#4a7bb8": "#46b6ff",
    "#4a8de8": "#46b6ff", "#5a8fd8": "#46b6ff", "#5a90d0": "#46b6ff",
    "#5a9af0": "#46b6ff", "#5ab4ff": "#46b6ff", "#5aa8ff": "#7bceff",
    "#6ba6f5": "#7bceff",
    # light blue text
    "#6f9ac8": "#9bddff", "#7ea4d0": "#9bddff", "#7fa8d8": "#9bddff",
    "#82a8d2": "#9bddff", "#7cbaff": "#9bddff", "#8cc4f5": "#9bddff",
    "#8cccff": "#9bddff", "#a8d0f5": "#c4e8ff", "#b8dafa": "#c4e8ff",
    "#c2ddf5": "#c4e8ff",
}

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
_RADIUS_RE = re.compile(
    r"((?:border(?:-(?:top|bottom)-(?:left|right))?-radius)\s*:\s*)(\d+(?:\.\d+)?)px")

_SRC_PROP = "_modpanel_qss_src"
_LOOK_PROP = "_modpanel_qss_look"

_state = {"style": DEFAULT_STYLE}


def normalize_style(name):
    name = str(name or "").strip().lower()
    return name if name in STYLE_LABELS else DEFAULT_STYLE


def current_style():
    return _state["style"]


def set_style(name):
    """Set the active style without restyling (use ``apply_style`` for live)."""
    _state["style"] = normalize_style(name)
    return _state["style"]


def col(hex_colour):
    """Translate one classic colour string into the active style."""
    if _state["style"] != "modpanel" or not isinstance(hex_colour, str):
        return hex_colour
    return _MODPANEL_COLOURS.get(hex_colour.strip().lower(), hex_colour)


def qcol(hex_colour):
    return QtGui.QColor(col(hex_colour))


def radius(value):
    """Translate a classic corner radius (px) into the active style."""
    if _state["style"] != "modpanel":
        return value
    if value <= 1:
        return int(value)
    return max(2, int(round(value * 0.4)))


def _soften_radius(match):
    return "{}{}px".format(match.group(1), radius(float(match.group(2))))


_BLOCK_RE = re.compile(r"([^{}]*)\{([^{}]*)\}")
_BG_DECL_RE = re.compile(r"(background(?:-color)?\s*:\s*)([^;{}]+)(;?)", re.I)
_WHITE_TEXT_RE = re.compile(r"(?<![-\w])(color\s*:\s*)#fff(?:fff)?\b", re.I)
_BORDER_NONE_RE = re.compile(r"(?<![-\w])border\s*:\s*none\s*;?", re.I)
_BORDER_DECL_RE = re.compile(r"(?<![-\w])border\s*:", re.I)
_BUTTON_SELECTORS = ("QPushButton", "QToolButton", "QTabBar::tab")
_ACCENT = "#46b6ff"
_ACCENT_HI = "#7bceff"
_ACCENT_BG = "#030b10"
_ACCENT_BG_HI = "#081d2b"


def _outline_accent_block(match):
    """ModPanel buttons never use a solid accent fill: like the reference
    design, primary buttons are a near-black fill with an accent outline and
    accent text."""
    selector, body = match.group(1), match.group(2)
    if not any(s in selector for s in _BUTTON_SELECTORS):
        return match.group(0)
    bg = _BG_DECL_RE.search(body)
    if not bg:
        return match.group(0)
    value = bg.group(2).lower()
    if _ACCENT in value:
        new_bg = _ACCENT_BG
    elif _ACCENT_HI in value:
        new_bg = _ACCENT_BG_HI
    else:
        return match.group(0)
    body = _BG_DECL_RE.sub(lambda m: "{}{};".format(m.group(1), new_bg), body, count=1)
    hover_state = any(s in selector for s in (":hover", ":pressed"))
    edge = _ACCENT_HI if hover_state else _ACCENT
    body = _WHITE_TEXT_RE.sub(lambda m: m.group(1) + edge, body)
    if _BORDER_NONE_RE.search(body):
        body = _BORDER_NONE_RE.sub("border:1px solid {};".format(edge), body)
    elif not _BORDER_DECL_RE.search(body):
        if hover_state:
            body = body.rstrip() + " border-color:{}; ".format(edge)
        else:
            body = body.rstrip() + " border:1px solid {}; ".format(edge)
    return "{}{{{}}}".format(selector, body)


def translate(qss, look=False):
    """Translate a classic stylesheet into the active style.

    ``look=True`` marks stylesheets whose radii already come from the user's
    Look settings, so only colours are translated there.
    """
    if not qss or _state["style"] != "modpanel":
        return qss
    out = _HEX_RE.sub(
        lambda m: _MODPANEL_COLOURS.get(m.group(0).lower(), m.group(0)), qss)
    if not look:
        out = _BLOCK_RE.sub(_outline_accent_block, out)
        out = _RADIUS_RE.sub(_soften_radius, out)
    return out


def set_qss(widget, qss, look=False):
    """Style ``widget`` with a classic-authored stylesheet in the active style."""
    qss = qss or ""
    try:
        widget.setProperty(_SRC_PROP, qss)
        widget.setProperty(_LOOK_PROP, bool(look))
    except Exception:
        pass
    widget.setStyleSheet(translate(qss, look))


def set_qss_look(widget, qss):
    """``set_qss`` for stylesheets whose radii come from the Look settings."""
    set_qss(widget, qss, look=True)


def restyle_all():
    """Re-translate every live plugin widget from its stored source stylesheet."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for widget in app.allWidgets():
        try:
            src = widget.property(_SRC_PROP)
        except Exception:
            continue
        if src is None:
            continue
        try:
            widget.setStyleSheet(translate(src, bool(widget.property(_LOOK_PROP))))
            widget.update()
        except Exception:
            pass


def look_preset(name):
    return dict(LOOK_PRESETS[normalize_style(name)])


def migrate_classic_look(look):
    """Convert Look values still at their classic defaults to ModPanel's,
    leaving any value the user customised untouched."""
    out = dict(look) if isinstance(look, dict) else {}
    classic = LOOK_PRESETS["classic"]
    modern = LOOK_PRESETS["modpanel"]
    for key, value in classic.items():
        cur = out.get(key)
        same = (str(cur or "").strip().lower() == value
                if isinstance(value, str) else cur == value)
        if same:
            out[key] = modern[key]
    return out
