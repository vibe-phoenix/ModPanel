# -*- coding: utf-8 -*-
"""Entry point for PhoenixPanel. Singleton per tab — recreated on tab switch."""

from __future__ import annotations

import importlib

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

_WINDOW_INSTANCE = None


def _remove_legacy_mb5_watcher():
    """Uninstall the Mouse Button 5 watcher an older version may have left on
    the QApplication (it survives module reloads), so MB5 no longer opens
    the panel in an already-running Maya session."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    w = getattr(app, "_phoenix_mb5_watcher", None)
    if w is None:
        return
    try:
        app.removeEventFilter(w)
    except Exception:
        pass
    try:
        w.enabled = False
    except Exception:
        pass
    try:
        del app._phoenix_mb5_watcher
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Panel open / singleton logic
# ---------------------------------------------------------------------------

def open_phoenix_panel():
    global _WINDOW_INSTANCE

    # ── Step 1: hide any visible panel IMMEDIATELY, before anything else.
    if _WINDOW_INSTANCE is not None:
        try:
            if _WINDOW_INSTANCE.isVisible():
                _WINDOW_INSTANCE.hide()
        except RuntimeError:
            _WINDOW_INSTANCE = None

    # ── Step 2: detect desired tab.
    from .core import _detect_desired_tab
    _tab_workspaces = None
    if _WINDOW_INSTANCE is not None:
        _tab_workspaces = getattr(_WINDOW_INSTANCE, "tab_workspaces", None)
    desired_tab = _detect_desired_tab(_tab_workspaces)

    from .utils import get_maya_main_window
    from .core import PhoenixPanel

    # ── Step 3: liveness check
    if _WINDOW_INSTANCE is not None:
        try:
            _WINDOW_INSTANCE.isVisible()
        except RuntimeError:
            _WINDOW_INSTANCE = None

    # ── Step 4: destroy instance if tab changed
    if _WINDOW_INSTANCE is not None and _WINDOW_INSTANCE.current_tab != desired_tab:
        try:
            _WINDOW_INSTANCE.close()
            _WINDOW_INSTANCE.deleteLater()
        except Exception:
            pass
        _WINDOW_INSTANCE = None

    # ── Step 5: create if needed, pre-load correct tab
    if _WINDOW_INSTANCE is None:
        parent = get_maya_main_window()
        _WINDOW_INSTANCE = PhoenixPanel(parent=parent)
        _WINDOW_INSTANCE.current_tab = desired_tab
        _WINDOW_INSTANCE.load_tab_config(desired_tab)

    # ── Step 6: show at cursor on correct tab
    _WINDOW_INSTANCE.show_at_cursor(desired_tab=desired_tab)


def preload_phoenix_panel():
    """Do everything a first open would do, without showing the panel.

    Builds the panel for the tab it would open on and resolves the icons of
    every panel's buttons, hot buttons and pie commands into the shared icon
    cache, so the first real open (on any tab) is as fast as later ones.
    Safe to call more than once; never raises.
    """
    global _WINDOW_INSTANCE

    if _WINDOW_INSTANCE is not None:
        try:
            _WINDOW_INSTANCE.isVisible()
            return _WINDOW_INSTANCE
        except RuntimeError:
            _WINDOW_INSTANCE = None

    try:
        from .core import PhoenixPanel, _detect_desired_tab, _TOTAL_TABS
        from .utils import get_maya_main_window
        desired_tab = _detect_desired_tab(None)
        panel = PhoenixPanel(parent=get_maya_main_window())
    except Exception as e:
        _warn("could not preload the panel: {}".format(e))
        return None

    def _warm(info):
        if not isinstance(info, dict):
            return
        try:
            panel._resolve_info_icon(info)
        except Exception:
            pass
        for cmd in info.get("pie_commands") or []:
            try:
                panel._resolve_pie_icon(cmd.get("icon", ""), cmd)
            except Exception:
                pass

    for tab in range(_TOTAL_TABS):
        try:
            panel.load_tab_config(tab)
        except Exception:
            continue
        for info in list(panel.buttons_data):
            _warm(info)
    for info in list(panel.custom_buttons):
        _warm(info)

    try:
        panel.current_tab = desired_tab
        panel.load_tab_config(desired_tab)
        panel._ensure_ui_built()
        panel.ensurePolished()
        panel.winId()               # create the native window up front
    except Exception as e:
        _warn("could not prebuild the panel UI: {}".format(e))

    # Import the windows opened from the panel so their first open is quick too.
    for name in ("settings", "pie_editor", "shelf_picker", "free_stuff"):
        try:
            importlib.import_module("." + name, __package__)
        except Exception:
            pass

    _WINDOW_INSTANCE = panel
    return panel


def _warn(message):
    try:
        import maya.cmds as cmds
        cmds.warning("ModPanel: " + message)
    except Exception:
        print("ModPanel: " + message)


if __name__ == "__main__":
    open_phoenix_panel()


try:
    _remove_legacy_mb5_watcher()
except Exception:
    pass
