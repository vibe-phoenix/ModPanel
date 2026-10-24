# -*- coding: utf-8 -*-
"""Button widget for PhoenixPanel.

Reposition mode is owned by the PANEL (core.py), not the button.
Buttons just report mouse events upward via signals and accept style commands.
"""

from __future__ import annotations

import math
import html

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from . import theme as _theme


class _GhostLabel(QtWidgets.QLabel):
    """Semi-transparent floating pixmap that follows the cursor."""

    def __init__(self, pixmap, parent=None):
        super(_GhostLabel, self).__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.ToolTip |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )
        # NOTE: do NOT set WindowTransparentForInput — we need widgetAt() to
        # skip it, which we handle in the panel by temporarily hiding it.
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)

        faded = QtGui.QPixmap(pixmap.size())
        faded.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(faded)
        p.setOpacity(0.72)
        p.drawPixmap(0, 0, pixmap)
        p.end()

        self.setPixmap(faded)
        self.resize(faded.size())

    def move_center_to(self, global_pos):
        self.move(global_pos - QtCore.QPoint(self.width() // 2, self.height() // 2))


class _PieDimOverlay(QtWidgets.QWidget):
    """Translucent black backdrop shown behind an open pie menu, to make the
    pie items stand out. A separate top-level window (not a child widget of
    the panel) so it can cover either just the panel or the whole Maya
    window depending on configuration, and so it can sit above everything
    except the pie itself in z-order.

    A rectangular hole is cut out (via setMask) over the source/origin
    button, so that button stays visibly undimmed along with the pie —
    the pie doesn't need its own hole since it's already a separate
    always-on-top window rendered above this overlay regardless of masking.
    """

    def __init__(self, geometry, source_rect_global=None, target_opacity=0.55,
                 source_radius=0, parent=None):
        flags = (QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint |
                 QtCore.Qt.NoDropShadowWindowHint |
                 QtCore.Qt.WindowTransparentForInput)
        super(_PieDimOverlay, self).__init__(parent, flags)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        # NOTE: deliberately NOT using a QSS "background-color" here — a
        # plain QWidget doesn't paint its stylesheet background unless
        # WA_StyledBackground is also set, which is an easy way for this to
        # silently render as fully transparent. paintEvent() below fills
        # the widget directly instead, which always works regardless.
        self._target_opacity = max(0.0, min(1.0, target_opacity))
        self._anim = None
        self._fade_ms = 150
        self._dismissing = False
        self.setWindowOpacity(0.0)
        self.setGeometry(geometry)

        if source_rect_global is not None and source_rect_global.isValid():
            local_hole = source_rect_global.translated(-geometry.topLeft())
            full = QtGui.QRegion(self.rect())
            if source_radius > 0:
                path = QtGui.QPainterPath()
                path.addRoundedRect(QtCore.QRectF(local_hole), source_radius, source_radius)
                hole = QtGui.QRegion(path.toFillPolygon().toPolygon())
            else:
                hole = QtGui.QRegion(local_hole)
            self.setMask(full.subtracted(hole))

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 255))
        p.end()

    def fade_in(self, delay_ms, fade_ms):
        self._fade_ms = max(0, int(fade_ms))
        self.show()

        def _start():
            if not self.isVisible():
                return
            anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(self._fade_ms)
            anim.setStartValue(self.windowOpacity())
            anim.setEndValue(self._target_opacity)
            anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped
                       if hasattr(QtCore.QAbstractAnimation, "DeletionPolicy")
                       else QtCore.QAbstractAnimation.DeleteWhenStopped)
            self._anim = anim

        if delay_ms <= 0:
            _start()
        else:
            QtCore.QTimer.singleShot(int(delay_ms), _start)

    def dismiss(self):
        """Fade out (same duration as the fade-in) and hide/delete once
        that finishes, instead of disappearing instantly. Safe to call
        more than once — only the first call starts anything."""
        if self._dismissing:
            return
        self._dismissing = True
        try:
            if self._anim is not None:
                self._anim.stop()
        except Exception:
            pass

        if self._fade_ms <= 0 or self.windowOpacity() <= 0.0:
            self._finalize()
            return

        anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(self._fade_ms)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.finished.connect(self._finalize)
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped
                   if hasattr(QtCore.QAbstractAnimation, "DeletionPolicy")
                   else QtCore.QAbstractAnimation.DeleteWhenStopped)
        self._anim = anim

    def _finalize(self):
        try:
            self.hide()
        except Exception:
            pass
        self.deleteLater()


class _PieItem(object):
    __slots__ = ("data", "center", "rect", "icon")

    def __init__(self, data, center, rect, icon):
        self.data   = data
        self.center = center
        self.rect   = rect
        self.icon   = icon


class PieMenuWidget(QtWidgets.QWidget):
    """Frameless radial pie/marking menu.

    Grabs the mouse (and keyboard, for Escape) for its entire lifetime —
    the caller has already pressed-and-held a source button, so from this
    point on every further mouse move/release belongs to the pie, no matter
    what's underneath the cursor. This sidesteps the need for any app-wide
    event filter: releasing the grabbed mouse button is what ends the
    interaction, exactly like Maya's own marking menus.

    Items are custom-painted (not real child widgets) so hit-testing and
    hover highlighting stay simple and reliable while the mouse is grabbed.

    Signals:
        commandSelected(dict) — emitted with the chosen pie-command dict
        cancelled()           — emitted when released over the source
                                 button / empty space, on Escape, or if the
                                 host application loses focus
    """

    commandSelected = QtCore.Signal(dict)
    cancelled       = QtCore.Signal()

    TOOLTIP_DELAY_MS   = 500
    MIN_ITEM_SPACING   = 12   # px gap between source button and ring
    RING_MARGIN        = 26   # px breathing room around the outer ring

    def __init__(self, source_global_center, source_size, pie_commands,
                 item_size, icon_resolver, start_angle=-90.0, parent=None,
                 dim_settings=None):
        flags = (QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint |
                 QtCore.Qt.NoDropShadowWindowHint)
        super(PieMenuWidget, self).__init__(parent, flags)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        self._commands      = list(pie_commands)[:6]
        self._item_size     = item_size
        self._src_size      = source_size
        self._icon_resolver = icon_resolver
        self._hover_index   = -1
        self._src_center_global = source_global_center
        self._items         = []
        self._finished      = False
        self._app_state_connected = False
        self._dim_settings  = dim_settings or {}
        self._dim_overlay   = None

        self._tooltip_timer = QtCore.QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.timeout.connect(self._show_hover_tooltip)

        self._build_layout(start_angle)

    # ------------------------------------------------------------ layout
    def _build_layout(self, start_angle):
        n = len(self._commands)
        radius = (self._src_size / 2.0 + self._item_size / 2.0 +
                  self.MIN_ITEM_SPACING)

        # The glow extends beyond the item by 55% of its hovered size.
        # Reserve that full halo in the popup geometry so left/right/top/
        # bottom items are never clipped by the window edge.
        hover_size = self._item_size + 8  # _paint_item grows 4px per side
        glow_margin = int(math.ceil(hover_size * 0.55)) + 4
        ring_margin = max(self.RING_MARGIN, glow_margin)
        half_span = radius + self._item_size / 2.0 + ring_margin
        span = int(half_span * 2)
        self.resize(span, span)

        screen = None
        try:
            screen = QtWidgets.QApplication.screenAt(self._src_center_global)
        except Exception:
            screen = None
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)

        x = self._src_center_global.x() - span // 2
        y = self._src_center_global.y() - span // 2
        x = max(geo.left(), min(x, geo.right() - span))
        y = max(geo.top(),  min(y, geo.bottom() - span))
        self.move(x, y)

        local_center = QtCore.QPoint(self._src_center_global.x() - x,
                                      self._src_center_global.y() - y)

        if n <= 0:
            self._items = []
            return
        if n == 1:
            angles = [start_angle]
        else:
            step = 360.0 / n
            angles = [start_angle + step * i for i in range(n)]

        self._items = []
        for cmd, ang in zip(self._commands, angles):
            rad = math.radians(ang)
            cx = local_center.x() + radius * math.cos(rad)
            cy = local_center.y() + radius * math.sin(rad)
            rect = QtCore.QRect(0, 0, self._item_size, self._item_size)
            rect.moveCenter(QtCore.QPoint(int(cx), int(cy)))
            icon = None
            icon_name = (cmd.get("icon") or "").strip() if isinstance(cmd, dict) else ""
            if (icon_name or (isinstance(cmd, dict) and cmd.get("icon_candidates"))) and self._icon_resolver:
                try:
                    icon = self._icon_resolver(icon_name, cmd)
                except TypeError:
                    try:
                        icon = self._icon_resolver(icon_name)
                    except Exception:
                        icon = None
                except Exception:
                    icon = None
            self._items.append(_PieItem(cmd, QtCore.QPoint(int(cx), int(cy)), rect, icon))

    # ------------------------------------------------------------ lifecycle
    def start(self):
        if not self._items:
            # Nothing configured — nothing to show; cancel immediately.
            QtCore.QTimer.singleShot(0, self.cancel_now)
            return
        # Set up (and show, at 0 opacity) the dim overlay BEFORE the pie
        # itself, then explicitly raise the pie — guarantees the pie always
        # stacks above the overlay regardless of window-manager quirks
        # around multiple WindowStaysOnTopHint windows.
        self._setup_dim_overlay()
        self.show()
        self.raise_()
        self.grabMouse()
        self.grabKeyboard()
        # Seed the initial hover from the current cursor position so a
        # release with zero mouse movement still commits the nearest item
        # rather than leaving _hover_index at its unset -1.
        try:
            cursor_pos = self.mapFromGlobal(QtGui.QCursor.pos())
        except Exception:
            cursor_pos = self.rect().center()
        self._hover_index = self._nearest_index(cursor_pos)
        self.update()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            try:
                app.applicationStateChanged.connect(self._on_app_state_changed)
                self._app_state_connected = True
            except Exception:
                self._app_state_connected = False

    def _setup_dim_overlay(self):
        cfg = self._dim_settings
        if not cfg or not cfg.get("enabled", False):
            return
        geometry = cfg.get("dim_rect")
        if geometry is None or not geometry.isValid():
            return
        try:
            overlay = _PieDimOverlay(
                geometry,
                source_rect_global=cfg.get("source_rect"),
                target_opacity=cfg.get("opacity", 0.55),
                source_radius=cfg.get("source_radius", 0),
                parent=self.parentWidget(),
            )
        except Exception:
            return
        self._dim_overlay = overlay
        overlay.fade_in(cfg.get("delay_ms", 150), cfg.get("fade_ms", 200))

    def cancel_now(self):
        """Force-cancel without waiting for a mouse release — used when the
        host panel is closing, hidden, or loses focus while a pie is open."""
        if self._finished:
            return
        self._hover_index = -1
        self._finish()

    def _on_app_state_changed(self, state):
        if state != QtCore.Qt.ApplicationActive:
            self.cancel_now()

    # ------------------------------------------------------------ painting
    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Subtle dot marking the source button's center — purely visual,
        # reinforces that the pie "grows out of" the button it came from.
        center_pen = _theme.qcol("#5a90d0"); center_pen.setAlpha(110)
        p.setPen(QtGui.QPen(center_pen, 1))
        _center_fill = _theme.qcol("#5a90d0"); _center_fill.setAlpha(60)
        p.setBrush(_center_fill)
        c = self.rect().center()
        p.drawEllipse(c, 4, 4)

        for idx, item in enumerate(self._items):
            self._paint_item(p, item, idx == self._hover_index)
        p.end()

    def _paint_item(self, p, item, hovered):
        rect = QtCore.QRectF(item.rect)
        if hovered:
            grow = 4
            rect.adjust(-grow, -grow, grow, grow)

        # Soft glow halo so items read clearly against a dimmed background —
        # every item gets a subtle ambient glow, brighter and wider on the
        # currently-hovered one. Painted as a radial gradient rather than a
        # real blur/graphics effect, which QPainter doesn't do natively.
        glow_color = _theme.qcol("#6ba6f5") if hovered else _theme.qcol("#3d6bb0")
        glow_alpha = 130 if hovered else 60
        glow_pad = rect.width() * (0.55 if hovered else 0.35)
        glow_rect = rect.adjusted(-glow_pad, -glow_pad, glow_pad, glow_pad)
        glow = QtGui.QRadialGradient(glow_rect.center(), glow_rect.width() / 2.0)
        c_in = QtGui.QColor(glow_color); c_in.setAlpha(glow_alpha)
        c_out = QtGui.QColor(glow_color); c_out.setAlpha(0)
        glow.setColorAt(0.0, c_in)
        glow.setColorAt(1.0, c_out)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(glow_rect)

        path = QtGui.QPainterPath()
        _r = _theme.radius(10)
        path.addRoundedRect(rect, _r, _r)

        bg     = _theme.qcol("#28304a") if hovered else _theme.qcol("#202432")
        border = _theme.qcol("#5a90d0") if hovered else _theme.qcol("#33395a")
        p.setPen(QtGui.QPen(border, 2 if hovered else 1))
        p.setBrush(bg)
        if hovered:
            p.setBrush(_theme.qcol("#28304a"))
            shadow = QtGui.QColor(0, 0, 0, 90)
            p.setPen(QtGui.QPen(shadow, 4))
            p.drawPath(path)
            p.setPen(QtGui.QPen(border, 2))
        p.setBrush(bg)
        p.drawPath(path)

        if item.icon is not None and not item.icon.isNull():
            # Box size already reflects pie_icon_scale (see _open_pie), so
            # the icon just fills a fixed fraction of whatever box it's in.
            frac = 0.72
            side = rect.width() * frac
            icon_rect = QtCore.QRectF(0, 0, side, side)
            icon_rect.moveCenter(rect.center())
            item.icon.paint(p, icon_rect.toRect(), QtCore.Qt.AlignCenter)

    # ------------------------------------------------------------ hit-testing
    def _nearest_index(self, pos):
        """Always returns the item closest to `pos` — no minimum-distance
        cutoff. This is what both hover highlighting and execute-on-release
        use, so whichever item is nearest the cursor is always the one that
        fires, exactly like a marking menu: there's no dead zone where
        releasing does nothing."""
        if not self._items:
            return -1
        best, best_d = 0, None
        for i, item in enumerate(self._items):
            dx = pos.x() - item.center.x()
            dy = pos.y() - item.center.y()
            dist2 = dx * dx + dy * dy
            if best_d is None or dist2 < best_d:
                best_d, best = dist2, i
        return best

    # ------------------------------------------------------------ tooltip
    def _show_hover_tooltip(self):
        if not (0 <= self._hover_index < len(self._items)):
            return
        item = self._items[self._hover_index]
        cmd = item.data if isinstance(item.data, dict) else {}
        name = (cmd.get("name") or "").strip() or "Command"
        tip  = (cmd.get("tooltip") or "").strip()
        ctype = "Python" if (cmd.get("type") or "mel").lower() == "python" else "MEL"
        lines = ["<b>{}</b>".format(html.escape(name))]
        if tip:
            lines.append(html.escape(tip))
        lines.append("<i>{}</i>".format(ctype))
        txt = "<html>{}</html>".format("<br>".join(lines))
        QtWidgets.QToolTip.showText(self.mapToGlobal(item.rect.center()), txt,
                                     self, item.rect)

    # ------------------------------------------------------------ mouse / keys
    def mouseMoveEvent(self, event):
        try:
            pos = event.pos()
        except AttributeError:
            pos = event.position().toPoint()
        idx = self._nearest_index(pos)
        if idx != self._hover_index:
            self._hover_index = idx
            self._tooltip_timer.stop()
            QtWidgets.QToolTip.hideText()
            if idx >= 0:
                self._tooltip_timer.start(self.TOOLTIP_DELAY_MS)
            self.update()

    def mousePressEvent(self, event):
        # Right-click cancels the pie immediately, regardless of what's
        # currently hovered — a quick, deliberate "back out" gesture while
        # the left button is still held to keep the pie open.
        if event.button() == QtCore.Qt.RightButton:
            self._hover_index = -1
            self._finish()
            return
        super(PieMenuWidget, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self._hover_index = -1
            self._finish()
            return
        if event.button() == QtCore.Qt.LeftButton:
            # Commit whatever is nearest the cursor right now — always a
            # valid item, never a dead zone.
            self._finish()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self._hover_index = -1
            self._finish()
        else:
            super(PieMenuWidget, self).keyPressEvent(event)

    def hideEvent(self, event):
        # Fallback: if something else hides this widget (e.g. the host
        # panel closing) without going through _finish(), still cancel
        # cleanly instead of leaving a dangling grab / stale state.
        if not self._finished:
            self.cancel_now()
        super(PieMenuWidget, self).hideEvent(event)

    # ------------------------------------------------------------ finish
    def _finish(self):
        if self._finished:
            return
        self._finished = True
        self._tooltip_timer.stop()
        QtWidgets.QToolTip.hideText()
        if self._dim_overlay is not None:
            try:
                self._dim_overlay.dismiss()
            except Exception:
                pass
            self._dim_overlay = None
        if self._app_state_connected:
            try:
                QtWidgets.QApplication.instance().applicationStateChanged.disconnect(
                    self._on_app_state_changed)
            except Exception:
                pass
            self._app_state_connected = False
        try:
            self.releaseMouse()
        except Exception:
            pass
        try:
            self.releaseKeyboard()
        except Exception:
            pass

        idx = self._hover_index
        self.hide()
        chosen = None
        if 0 <= idx < len(self._items):
            chosen = self._items[idx].data
        self.deleteLater()

        if isinstance(chosen, dict):
            self.commandSelected.emit(chosen)
        else:
            self.cancelled.emit()


_BUTTON_THEME_DEFAULTS = {
    "button": "#202432",
    "button_hover": "#2a3042",
    "button_pressed": "#161a24",
    "button_selected": "#1e3050",
    "panel_border": "#303645",
    "text": "#f5f7ff",
    "icon": "#c8d2ff",
    "accent": "#4a7bb8",
    "border_thickness": 1,
    "corner_radius": 12,
    "button_padding": 6,
}


class PhoenixButtonWidget(QtWidgets.QWidget):
    """Single grid button. Reposition drag logic lives in the panel."""

    # Emitted on left-click (execute primary command)
    triggeredWithIndex   = QtCore.Signal(int)
    # Emitted on middle-click (execute double-click / secondary command)
    middleClickTriggered = QtCore.Signal(int)
    # Context-menu actions
    requestDelete        = QtCore.Signal(int)
    requestReposition    = QtCore.Signal(int)
    requestEditPie       = QtCore.Signal(int)   # "Edit Pie Commands"
    requestAddToPie      = QtCore.Signal(int)   # "Add to Another Button's Pie"
    requestEditLabel     = QtCore.Signal(int)   # "Edit Label"
    requestChangeIcon    = QtCore.Signal(int, str)  # source: shelf/local/clear
    requestToggleCloseBehavior = QtCore.Signal(int)  # inverse of global Close on click
    # Emitted when a pie command is chosen (release over a pie item)
    pieCommandTriggered  = QtCore.Signal(int, dict)

    # Fallback used only if the panel (or its pie_hold_delay_ms attribute)
    # can't be reached for some reason — normal path reads the live,
    # user-configurable value via self.window().pie_hold_delay_ms.
    HOLD_THRESHOLD_MS = 100

    def __init__(self, index, overlay_label, icon, tooltip, parent=None):
        super(PhoenixButtonWidget, self).__init__(parent)
        self.index = index
        self._is_destroyed = False
        self._theme = dict(_BUTTON_THEME_DEFAULTS)

        # Pie-menu state — configured post-construction via configure_pie()
        self.pie_provider    = None   # callable(index) -> list[dict]
        self.angle_provider  = None   # callable(index) -> float or None (per-button rotation override)
        self.icon_resolver   = None   # callable(icon_name) -> QIcon
        self._main_icon_name = ""
        self._main_tooltip_text = tooltip or ""
        self._press_button   = None
        self._active_pie     = None

        self._hold_timer = QtCore.QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_timeout)

        self.tool_btn = QtWidgets.QToolButton(self)
        self.tool_btn.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self.tool_btn.setIcon(icon)
        self.refresh_tooltip()

        self.overlay = QtWidgets.QLabel(overlay_label, self.tool_btn)
        self.overlay.setAlignment(QtCore.Qt.AlignCenter)
        self.overlay.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.has_label = bool(overlay_label and overlay_label.strip())
        if self.has_label:
            self._apply_overlay_style()
        else:
            _theme.set_qss(self.overlay, "background: transparent; color: transparent;")
            self.overlay.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tool_btn)

        self.tool_btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tool_btn.customContextMenuRequested.connect(self._show_menu)
        self.tool_btn.clicked.connect(
            lambda checked=False: self.triggeredWithIndex.emit(self.index)
        )
        # Middle-click → secondary (double-click) command
        self.tool_btn.installEventFilter(self)

        self._normal_style()

    # ---------------------------------------------------------------- theme
    def _look(self):
        out = dict(_BUTTON_THEME_DEFAULTS)
        if isinstance(getattr(self, "_theme", None), dict):
            out.update(self._theme)
        return out

    def set_theme(self, theme):
        if isinstance(theme, dict):
            self._theme = dict(_BUTTON_THEME_DEFAULTS)
            self._theme.update(theme)
        else:
            self._theme = dict(_BUTTON_THEME_DEFAULTS)
        self._apply_overlay_style()
        self._normal_style()

    def _apply_overlay_style(self):
        if not getattr(self, "has_label", False) or self._is_destroyed:
            return
        look = self._look()
        radius = max(0, min(12, int(look.get("corner_radius", 12) * 0.55)))
        _theme.set_qss_look(self.overlay, """
        QLabel {{
            background-color: rgba(0,0,0,170);
            color: {text};
            font-size: 9px;
            padding: 2px 3px;
            border-bottom-left-radius: {radius}px;
            border-bottom-right-radius: {radius}px;
        }}
        """.format(text=look.get("text", "#f5f7ff"), radius=radius))

    # ---------------------------------------------------------------- event filter
    def eventFilter(self, obj, event):
        """Own LC mouse handling on tool_btn so short-click and
        hold-to-open-pie can coexist without conflicting. Right-click is
        left completely untouched (native context menu), and buttons with
        no pie commands configured are left completely untouched on the
        left-click side too (native QToolButton click behaviour), so there
        is zero behavioural change for existing setups.

        "Add to Another Button's Pie" target-selection mode is deliberately
        NOT special-cased here — it's handled one layer up, inside the
        normal triggeredWithIndex -> _on_button_triggered pipeline (see
        core.py). Intercepting it at this level used to depend on Qt's
        exact event-filter dispatch order between the app-wide filter and
        this per-button filter, which is fragile; routing it through the
        click signal that already fires reliably for every other click
        avoids that entirely.
        """
        if obj is not self.tool_btn or self._is_destroyed:
            return super(PhoenixButtonWidget, self).eventFilter(obj, event)

        et = event.type()
        panel = self.window()

        # ── Reposition mode: hands-off, the panel's app-wide filter drives
        # the whole drag operation exactly as before. ──────────────────────
        if getattr(panel, "_reposition_mode", False):
            return False

        if et == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.MiddleButton:
                self.middleClickTriggered.emit(self.index)
                return True
            if event.button() == QtCore.Qt.LeftButton:
                if not self._current_pie_commands():
                    return False   # no pie configured — untouched native path
                self._press_button = event.button()
                self.tool_btn.setDown(True)
                delay = getattr(panel, "pie_hold_delay_ms", self.HOLD_THRESHOLD_MS)
                self._hold_timer.start(max(0, int(delay)))
                return True
            return False   # RightButton — always native (context menu)

        if et == QtCore.QEvent.MouseButtonRelease:
            if self._press_button is not None and event.button() == self._press_button:
                was_pending = self._hold_timer.isActive()
                self._hold_timer.stop()
                self._press_button = None
                self.tool_btn.setDown(False)
                if not was_pending:
                    # Hold threshold already fired — the pie (or a no-op,
                    # if pie_commands emptied out mid-hold, e.g. because
                    # target-selection mode started while held) already
                    # handled this press. Swallow the stray release.
                    return True
                if self.tool_btn.rect().contains(event.pos()):
                    self.triggeredWithIndex.emit(self.index)
                return True
            return False

        return super(PhoenixButtonWidget, self).eventFilter(obj, event)

    # ---------------------------------------------------------------- pie menu
    def configure_pie(self, pie_provider=None, icon_resolver=None, main_icon_name="",
                       angle_provider=None):
        """Wire this button into the pie-menu system. Called once right
        after construction (mirrors how signals are connected post-init).
        `pie_provider(index)` must return the live list of pie-command
        dicts for this button — read live rather than cached so edits made
        through 'Edit Pie Commands' / 'Add to Another Button's Pie' show up
        immediately without a full grid rebuild. `angle_provider(index)`
        returns this button's own pie-rotation override (float) or None to
        fall back to the panel-wide default."""
        self.pie_provider    = pie_provider
        self.angle_provider  = angle_provider
        self.icon_resolver   = icon_resolver
        self._main_icon_name = main_icon_name or ""
        self.refresh_tooltip()

    def _current_pie_commands(self):
        if not self.pie_provider:
            return []
        try:
            cmds = self.pie_provider(self.index) or []
        except Exception:
            cmds = []
        return [c for c in cmds if isinstance(c, dict) and (c.get("code") or "").strip()][:6]

    def refresh_tooltip(self, main_tooltip=None):
        """Rebuild the tooltip from current state. Safe to call anytime —
        e.g. after pie commands change — without touching layout or icons."""
        if self._is_destroyed:
            return
        if main_tooltip is not None:
            self._main_tooltip_text = main_tooltip
        pie_cmds = self._current_pie_commands()
        if not pie_cmds:
            self.tool_btn.setToolTip(self._main_tooltip_text or "")
            return
        try:
            from .utils import build_pie_tooltip_html, icon_data_uri
        except Exception:
            self.tool_btn.setToolTip(self._main_tooltip_text or "")
            return
        main_uri = icon_data_uri(self._main_icon_name) if self._main_icon_name else None
        pie_entries = []
        for cmd in pie_cmds:
            icon_name = cmd.get("icon", "")
            uri = icon_data_uri(icon_name) if icon_name else None
            label = (cmd.get("name") or "").strip() or "Command"
            pie_entries.append((uri, label))
        main_name = (self.overlay.text() if hasattr(self, "overlay") else "") or "Button"
        self.tool_btn.setToolTip(
            build_pie_tooltip_html(main_name, self._main_tooltip_text, main_uri, pie_entries)
        )

    def _on_hold_timeout(self):
        if self._press_button is None or self._is_destroyed:
            return
        panel = self.window()
        if getattr(panel, "_reposition_mode", False):
            return
        cmds = self._current_pie_commands()
        if not cmds:
            return   # pie emptied out mid-hold — no-op, release will be swallowed
        self._open_pie(cmds)

    def _open_pie(self, cmds):
        global_center = self.tool_btn.mapToGlobal(self.tool_btn.rect().center())
        src_size  = self.tool_btn.width()
        icon_scale = max(0.5, min(1.5, getattr(self.window(), "pie_icon_scale", 1.0)))
        base_item_size = max(20, min(int(src_size * 0.55), 56))
        item_size = max(16, min(int(round(base_item_size * icon_scale)), 84))
        resolver  = self.icon_resolver or (lambda name: QtGui.QIcon())
        parent_win = None
        try:
            from .utils import get_maya_main_window
            parent_win = get_maya_main_window()
        except Exception:
            parent_win = None

        dim_settings = self._build_dim_settings(global_center, src_size)
        override_angle = None
        if self.angle_provider is not None:
            try:
                override_angle = self.angle_provider(self.index)
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
            "source_radius": max(0, int(self._look().get("corner_radius", 12))),
            "delay_ms": getattr(panel, "pie_dim_delay_ms", 150),
            "fade_ms":  getattr(panel, "pie_dim_fade_ms", 200),
            "opacity":  max(0.1, min(1.0, opacity_pct / 100.0)),
        }

    def _apply_origin_glow(self):
        # A QGraphicsDropShadowEffect rasterizes the widget's full
        # rectangular bounding box before blurring it, which on a rounded
        # button tends to show up as a boxy halo rather than a soft glow —
        # so this uses a stylesheet swap instead (same technique as
        # _drop_target_style / set_pie_target_style above), which stays
        # properly rounded since it's drawn as part of the button itself.
        if self._is_destroyed:
            return
        v = self._style_values()
        _theme.set_qss_look(self.tool_btn, """
        QToolButton {{
            background-color: {selected}; border-radius: {radius}px;
            padding: {padding}px; border: 2px solid {accent};
        }}
        """.format(**v))

    def _clear_origin_glow(self):
        self._normal_style()

    def _on_pie_selected(self, cmd):
        self._active_pie = None
        self._clear_origin_glow()
        if not self._is_destroyed:
            self.pieCommandTriggered.emit(self.index, cmd)

    def _on_pie_cancelled(self):
        self._active_pie = None
        self._clear_origin_glow()

    def cancel_active_pie(self):
        """Force-close any open pie belonging to this button — called by
        the panel when it's hiding/closing so a held pie never outlives
        its host."""
        if self._active_pie is not None:
            try:
                self._active_pie.cancel_now()
            except Exception:
                pass
            self._active_pie = None

    # ---------------------------------------------------------------- sizing
    def set_sizes(self, side, icon_size):
        padding = max(0, int(self._look().get("button_padding", 6)))
        total = side + padding * 2
        self.setFixedSize(total, total)
        self.tool_btn.setFixedSize(total, total)
        self.tool_btn.setIconSize(QtCore.QSize(icon_size, icon_size))

    def resizeEvent(self, event):
        super(PhoenixButtonWidget, self).resizeEvent(event)
        if self.has_label and not self._is_destroyed:
            w = self.tool_btn.width()
            h = self.tool_btn.height()
            lh = max(16, int(h * 0.32))
            self.overlay.setGeometry(0, h - lh, w, lh)

    def set_overlay_label(self, text):
        """Live-update the bottom overlay label — no grid rebuild needed,
        the label doesn't affect the button's own size."""
        if self._is_destroyed:
            return
        text = (text or "").strip()
        self.overlay.setText(text)
        self.has_label = bool(text)
        if self.has_label:
            self._apply_overlay_style()
            self.overlay.show()
            w = self.tool_btn.width()
            h = self.tool_btn.height()
            lh = max(16, int(h * 0.32))
            self.overlay.setGeometry(0, h - lh, w, lh)
        else:
            _theme.set_qss(self.overlay, "background: transparent; color: transparent;")
            self.overlay.hide()

    # --------------------------------------------------------------- styles
    def _style_values(self):
        look = self._look()
        return {
            "button": look.get("button", "#202432"),
            "hover": look.get("button_hover", "#2a3042"),
            "pressed": look.get("button_pressed", "#161a24"),
            "selected": look.get("button_selected", "#1e3050"),
            "border_colour": look.get("panel_border", "#303645"),
            "text": look.get("text", "#f5f7ff"),
            "icon": look.get("icon", "#c8d2ff"),
            "accent": look.get("accent", "#4a7bb8"),
            "radius": max(0, min(32, int(look.get("corner_radius", 12)))),
            "padding": max(0, min(18, int(look.get("button_padding", 6)))),
            "border": max(0, min(8, int(look.get("border_thickness", 1)))),
        }

    def _normal_style(self):
        if self._is_destroyed:
            return
        v = self._style_values()
        _theme.set_qss_look(self.tool_btn, """
        QToolButton {{
            background-color: {button};
            color: {icon};
            border-radius: {radius}px;
            padding: {padding}px;
            border: {border}px solid {border_colour};
        }}
        QToolButton:hover {{ background-color: {hover}; border-color: {accent}; }}
        QToolButton:pressed {{ background-color: {pressed}; }}
        QToolTip {{
            background-color: #ffffdc; color: #000000;
            border: 1px solid #888888; padding: 1px 4px;
        }}
        """.format(**v))

    def _reposition_idle_style(self):
        if self._is_destroyed:
            return
        v = self._style_values()
        _theme.set_qss_look(self.tool_btn, """
        QToolButton {{
            background-color: {button}; border-radius: {radius}px;
            padding: {padding}px; border: {border}px dashed {accent};
        }}
        """.format(**v))

    def _dragging_source_style(self):
        if self._is_destroyed:
            return
        v = self._style_values()
        _theme.set_qss_look(self.tool_btn, """
        QToolButton {{
            background-color: {pressed}; border-radius: {radius}px;
            border: 2px dashed {border_colour};
        }}
        """.format(**v))

    def _drop_target_style(self):
        if self._is_destroyed:
            return
        v = self._style_values()
        _theme.set_qss_look(self.tool_btn, """
        QToolButton {{
            background-color: {selected}; border-radius: {radius}px;
            border: 2px solid {accent};
        }}
        """.format(**v))

    def set_pie_target_style(self, mode):
        if self._is_destroyed:
            return
        v = self._style_values()
        if mode == "source":
            _theme.set_qss_look(self.tool_btn, """
            QToolButton {{ background:{selected}; border-radius:{radius}px;
                padding:{padding}px; border:2px solid {accent}; }}
            """.format(**v))
        elif mode == "target":
            _theme.set_qss_look(self.tool_btn, """
            QToolButton {{ background:{button}; border-radius:{radius}px;
                padding:{padding}px; border:2px dashed {accent}; }}
            QToolButton:hover {{ background:{hover}; border-color:{accent}; }}
            """.format(**v))
        else:
            self._normal_style()

    # -------------------------------------------------------------- context menu
    def _show_menu(self, pos):
        if self._is_destroyed:
            return

        menu = QtWidgets.QMenu(self)
        menu.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        menu.setWindowFlags(
            menu.windowFlags() |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.NoDropShadowWindowHint
        )
        _theme.set_qss(menu, """
        QMenu {
            background-color: #212121;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            padding: 4px;
        }
        QMenu::item {
            color: #d6daf5;
            padding: 6px 16px;
            border-radius: 5px;
            font-size: 11px;
        }
        QMenu::item:selected {
            background-color: #2e2e2e;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background: #3a3a3a;
            margin: 3px 8px;
        }
        """)

        act_repos = menu.addAction("Reposition")
        act_edit_label = menu.addAction("Edit Label")
        icon_menu = menu.addMenu("Change Icon")
        act_icon_shelf = icon_menu.addAction("Choose from Shelf...")
        act_icon_local = icon_menu.addAction("Choose Local File...")
        act_icon_clear = icon_menu.addAction("Clear Icon")
        menu.addSeparator()
        act_edit_pie = menu.addAction("Edit Pie Commands")
        act_add_pie  = menu.addAction("Add to Another Button's Pie")

        # Per-button close override.  The setting is intentionally expressed
        # as the actual result, while the stored flag means "invert the global
        # Close on click setting". This keeps the UI obvious in either state.
        panel = self.window()
        global_close = bool(getattr(panel, "close_on_click", True))
        close_label = ("Keep Panel Open on Click" if global_close
                       else "Close Panel on Click")
        act_close_behavior = menu.addAction(close_label)
        act_close_behavior.setCheckable(True)
        try:
            info = panel.buttons_data[self.index]
            act_close_behavior.setChecked(bool(
                info.get("invert_close_on_click", False)))
        except Exception:
            act_close_behavior.setChecked(False)
        act_close_behavior.setToolTip(
            "When checked, this button does the opposite of Settings > Close on click. "
            "The same rule applies to its normal, middle-click, and pie-menu commands.")

        menu.addSeparator()
        act_del = menu.addAction("Delete")

        gpos   = self.tool_btn.mapToGlobal(pos)
        chosen = menu.exec_(gpos) if hasattr(menu, "exec_") else menu.exec(gpos)

        if not chosen:
            return
        if chosen == act_repos:
            self.requestReposition.emit(self.index)
        elif chosen == act_edit_label:
            self.requestEditLabel.emit(self.index)
        elif chosen == act_icon_shelf:
            self.requestChangeIcon.emit(self.index, "shelf")
        elif chosen == act_icon_local:
            self.requestChangeIcon.emit(self.index, "local")
        elif chosen == act_icon_clear:
            self.requestChangeIcon.emit(self.index, "clear")
        elif chosen == act_edit_pie:
            self.requestEditPie.emit(self.index)
        elif chosen == act_add_pie:
            self.requestAddToPie.emit(self.index)
        elif chosen == act_close_behavior:
            self.requestToggleCloseBehavior.emit(self.index)
        elif chosen == act_del:
            self.requestDelete.emit(self.index)

    # ---------------------------------------------------------------- cleanup
    def cleanup(self):
        if self._is_destroyed:
            return
        self._is_destroyed = True
        try:
            self._hold_timer.stop()
        except Exception:
            pass
        self.cancel_active_pie()
        try:
            if hasattr(self, "tool_btn") and self.tool_btn:
                self.tool_btn.removeEventFilter(self)
                try:
                    self.tool_btn.clicked.disconnect()
                except Exception:
                    pass
                try:
                    self.tool_btn.customContextMenuRequested.disconnect()
                except Exception:
                    pass
        except Exception:
            pass
        for sig in ("triggeredWithIndex", "middleClickTriggered",
                    "requestDelete", "requestReposition", "requestEditPie",
                    "requestAddToPie", "requestEditLabel", "requestChangeIcon",
                    "requestToggleCloseBehavior", "pieCommandTriggered"):
            try:
                getattr(self, sig).disconnect()
            except Exception:
                pass

    def __del__(self):
        self.cleanup()