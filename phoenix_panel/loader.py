# -*- coding: utf-8 -*-
"""Startup loader for ModPanel.

Called from userSetup.py. Once Maya's UI is ready it preloads ModPanel:
the panel is built hidden and every button, hot-button and pie icon is
resolved ahead of time, so the first open is as instant as later ones.
"""

from __future__ import annotations

# Set to True to also open the panel as soon as Maya finishes starting.
OPEN_ON_STARTUP = False


def _load():
    import maya.cmds as cmds
    try:
        import phoenix_panel
        from phoenix_panel import launcher
        launcher.preload_phoenix_panel()
        if OPEN_ON_STARTUP:
            phoenix_panel.open_phoenix_panel()
    except Exception as e:
        cmds.warning("ModPanel failed to load at startup: {}".format(e))


def load():
    """Schedule the ModPanel preload for once Maya's UI is ready."""
    import maya.utils
    try:
        # Run after Maya's own startup work so it never delays the UI.
        maya.utils.executeDeferred(_load, lowestPriority=True)
    except TypeError:
        maya.utils.executeDeferred(_load)
