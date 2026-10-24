# -*- coding: utf-8 -*-
"""Free Stuff — community scripts browser for PhoenixPanel.

Lists the contents of the public PhoenixPanel-Scripts GitHub repo
(one "scripts/<name>.py" paired with one "icons/<name>.<ext>" per item,
matched by filename with the extension stripped), downloads whichever
files are missing/out of date into a local cache on the user's machine,
and lets the user:

    * click an icon to view the script's source
    * "Run Once" it immediately in Maya without adding anything
    * "Add to Panel" it as a real button on any of the 7 PhoenixPanel
      tabs (Panel 1/2/3 or the hidden Q/W/E/R panels), linked to the
      downloaded file on disk (not a frozen copy of the code) so a
      later re-download picks up automatically.

This module is intentionally self-contained (no import of settings.py)
so it can be dropped in without touching the rest of the package other
than a single new tab entry in settings.py.
"""

from __future__ import annotations

import os
import json

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:  # Python 2 fallback, just in case
    from urllib2 import urlopen, Request, URLError, HTTPError  # type: ignore

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from . import theme as _theme


# ---------------------------------------------------------------------------
# Repo config
# ---------------------------------------------------------------------------

GITHUB_OWNER = "vibe-phoenix"
GITHUB_REPO = "PhoenixPanel-Scripts"
SCRIPTS_SUBDIR = "scripts"
ICONS_SUBDIR = "icons"

_API_BASE = "https://api.github.com/repos/{}/{}/contents".format(
    GITHUB_OWNER, GITHUB_REPO)
_USER_AGENT = "PhoenixPanel-FreeStuff"

_PANEL_LABELS = ["Panel 1", "Panel 2", "Panel 3", "Q", "W", "E"]


# ---------------------------------------------------------------------------
# Local palette (kept in sync with settings.py's _C by eye — duplicated
# here rather than imported, so this module never imports settings.py and
# there is no risk of a circular import).
# ---------------------------------------------------------------------------

_C = {
    "bg": "#0e1016", "surface": "#151824", "raise_": "#1b1f2d",
    "border": "#262b3d", "border2": "#323852", "focus": "#2f8fef",
    "text": "#f5f6fc", "dim": "#adb4d1", "hint": "#7d84a3",
    "input": "#0a0c12", "btn": "#1b1f2d", "hover": "#242a3d",
    "accent": "#2f8fef", "accent_h": "#5aa8ff", "accent_dim": "#1f3f66",
    "card": "#171b28", "red": "#e2495f",
}

_SS_SLIDER = """
QSlider::groove:horizontal {{ height:4px; background:{input}; border-radius:2px; }}
QSlider::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {accent_h}, stop:1 {accent});
    width:14px; height:14px; margin:-5px 0; border-radius:7px; border:1px solid {bg};
}}
QSlider::handle:horizontal:hover {{ background:{accent_h}; }}
QSlider::sub-page:horizontal {{ background:{accent}; border-radius:2px; }}
QSlider::add-page:horizontal {{ background:{border}; border-radius:2px; }}
""".format(**_C)

_SS_TOOLTIP = """
QToolTip {{
    background:{surface}; color:{text}; border:1px solid {border2};
    border-radius:4px; padding:4px 6px; font-size:10px;
}}
""".format(**_C)

_SS_BTN = """
QPushButton {{
    background:{btn}; color:{text}; border:1px solid {border};
    border-radius:6px; font-size:10px; padding:3px 8px;
}}
QPushButton:hover {{ background:{hover}; border-color:{border2}; }}
QPushButton:disabled {{ color:{hint}; }}
""".format(**_C) + _SS_TOOLTIP

_SS_BTN_ACCENT = """
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {accent_h}, stop:1 {accent});
    color:#fff; border:none; border-radius:6px; font-size:10px; font-weight:600; padding:3px 8px;
}}
QPushButton:hover {{ background:{accent_h}; }}
QPushButton:disabled {{ background:{border}; color:{hint}; }}
""".format(**_C) + _SS_TOOLTIP


# ---------------------------------------------------------------------------
# Local cache
# ---------------------------------------------------------------------------

def _cache_root():
    root = os.path.join(os.path.expanduser("~"), "PhoenixPanel", "FreeStuff")
    for sub in (SCRIPTS_SUBDIR, ICONS_SUBDIR):
        p = os.path.join(root, sub)
        if not os.path.isdir(p):
            try:
                os.makedirs(p)
            except Exception:
                pass
    return root


def _manifest_path():
    return os.path.join(_cache_root(), "_manifest.json")


def _load_manifest():
    p = _manifest_path()
    if os.path.isfile(p):
        try:
            with open(p, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_manifest(data):
    try:
        with open(_manifest_path(), "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def local_script_path(item):
    return os.path.join(_cache_root(), SCRIPTS_SUBDIR, item["script_name"])


def local_icon_path(item):
    if not item.get("icon_name"):
        return None
    return os.path.join(_cache_root(), ICONS_SUBDIR, item["icon_name"])


# ---------------------------------------------------------------------------
# Network (blocking — always call these from a worker thread)
# ---------------------------------------------------------------------------

def _http_get_json(url):
    req = Request(url, headers={"User-Agent": _USER_AGENT,
                                 "Accept": "application/vnd.github+json"})
    resp = urlopen(req, timeout=15)
    try:
        return json.loads(resp.read().decode("utf-8"))
    finally:
        resp.close()


def _http_get_bytes(url):
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    resp = urlopen(req, timeout=25)
    try:
        return resp.read()
    finally:
        resp.close()


def _base_name(name):
    return os.path.splitext(name)[0]


def _norm_key(name):
    """Normalize a base filename for matching scripts to icons: case and
    surrounding whitespace shouldn't matter (GitHub filenames are case
    sensitive, but people naming a script "MyTool.py" and an icon
    "mytool.png" is an easy, common mismatch)."""
    return _base_name(name).strip().lower()


def _gh_list_or_raise(path):
    result = _http_get_json("{}/{}".format(_API_BASE, path))
    if isinstance(result, list):
        return result
    # GitHub returns a dict (e.g. {"message": "Not Found", ...}) when the
    # path doesn't exist, the repo is private, or the rate limit was hit.
    message = result.get("message") if isinstance(result, dict) else None
    raise RuntimeError("'{}' folder: {}".format(path, message or "unexpected response"))


def fetch_catalog():
    """List scripts/ + icons/ from the repo and pair them by filename
    (extension stripped, case/whitespace-insensitive). Blocking — call
    off the main thread."""
    scripts = _gh_list_or_raise(SCRIPTS_SUBDIR)
    icons = _gh_list_or_raise(ICONS_SUBDIR)

    icon_by_base = {}
    for it in icons:
        if it.get("type") == "file":
            icon_by_base[_norm_key(it["name"])] = it

    catalog = []
    unmatched = []
    for it in scripts:
        if it.get("type") != "file":
            continue
        base = _base_name(it["name"])
        icon_entry = icon_by_base.get(_norm_key(it["name"]))
        if icon_entry is None:
            unmatched.append(base)
        catalog.append({
            "name": base,
            "script_name": it["name"],
            "script_url": it.get("download_url"),
            "script_sha": it.get("sha"),
            "icon_name": icon_entry["name"] if icon_entry else None,
            "icon_url": icon_entry.get("download_url") if icon_entry else None,
            "icon_sha": icon_entry.get("sha") if icon_entry else None,
        })
    catalog.sort(key=lambda d: d["name"].lower())
    catalog_unmatched = unmatched
    return catalog, catalog_unmatched


def ensure_local_files(item):
    """Download script + icon into the local cache if missing or out of
    date (tracked by GitHub blob sha in a small manifest). Blocking —
    call off the main thread. Returns (script_path, icon_path_or_None)."""
    manifest = _load_manifest()
    changed = False

    sp = local_script_path(item)
    if item.get("script_url"):
        stale = manifest.get(item["script_name"]) != item.get("script_sha")
        if stale or not os.path.isfile(sp):
            data = _http_get_bytes(item["script_url"])
            with open(sp, "wb") as f:
                f.write(data)
            manifest[item["script_name"]] = item.get("script_sha")
            changed = True

    ip = None
    try:
        ip = ensure_icon(item, manifest=manifest)
    except Exception:
        ip = local_icon_path(item)

    # ensure_icon() mutates `manifest` in place but (since we passed one
    # in) leaves saving to us — always save so a successful icon refresh
    # isn't lost just because the script itself was already up to date.
    _save_manifest(manifest)
    return sp, ip


def _looks_like_image(data):
    """Cheap sniff to catch the common failure mode: download_url pointed
    at something that isn't actually image bytes (a 404/rate-limit page,
    an HTML redirect, an empty file, ...). Checks magic bytes for the
    formats Qt/QPixmap can load without extra plugins."""
    if not data or len(data) < 8:
        return False
    sigs = (
        b"\x89PNG\r\n\x1a\n",         # PNG
        b"\xff\xd8\xff",              # JPEG
        b"GIF87a", b"GIF89a",         # GIF
        b"BM",                        # BMP
        b"RIFF",                      # WEBP (RIFF....WEBP)
    )
    return (any(data.startswith(sig) for sig in sigs)
            or (data[:5] == b"<?xml" and b"<svg" in data[:200]))


def ensure_icon(item, manifest=None):
    """Download just the icon (not the script) if missing or out of date.
    Blocking — call off the main thread. Returns the local icon path, or
    None if this item has no matching icon in the repo or the download
    didn't come back as usable image data (in which case nothing bad is
    cached — it'll just retry next refresh)."""
    ip = local_icon_path(item)
    if not ip or not item.get("icon_url"):
        return None

    own_manifest = manifest is None
    if own_manifest:
        manifest = _load_manifest()

    stale = manifest.get(item["icon_name"]) != item.get("icon_sha")
    if stale or not os.path.isfile(ip):
        data = _http_get_bytes(item["icon_url"])
        if not _looks_like_image(data):
            # Don't cache garbage under the real filename — remove any
            # previous (possibly also-bad) copy so this gets retried
            # instead of permanently showing the fallback icon.
            if os.path.isfile(ip):
                try:
                    os.remove(ip)
                except OSError:
                    pass
            raise RuntimeError(
                "downloaded data for '{}' doesn't look like an image".format(
                    item["icon_name"]))
        with open(ip, "wb") as f:
            f.write(data)
        manifest[item["icon_name"]] = item.get("icon_sha")
        if own_manifest:
            _save_manifest(manifest)
    return ip


def read_script_source(script_path):
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return "# Could not read script:\n# {}\n".format(e)


def build_button_info(item, script_path, icon_path):
    """Build a buttons_data-shaped dict, wired to run the *file on disk*
    (not a frozen copy of its text), so re-downloading the script later
    is picked up the next time the button is pressed."""
    loader = (
        "_fs_path = {sp!r}\n"
        "with open(_fs_path, 'r', encoding='utf-8') as _fs_f:\n"
        "    _fs_src = _fs_f.read()\n"
        "exec(compile(_fs_src, _fs_path, 'exec'), globals())\n"
    ).format(sp=script_path)
    return {
        "label": "",
        "name": item["name"],
        "annotation": "Free Stuff: {}".format(item["name"]),
        "icon": icon_path or "",
        "command": loader,
        "sourceType": "python",
        "pie_commands": [],
    }


def add_button_to_tab(panel_obj, tab_index, info):
    """Append `info` onto tab `tab_index` (0..6). If it's the live tab,
    goes through the normal in-memory + rebuild path; otherwise it's
    written straight into that tab's config file on disk, in the same
    shape save_tab_config() writes, without disturbing anything else
    already stored for that tab."""
    if tab_index == getattr(panel_obj, "current_tab", None):
        panel_obj.buttons_data.append(info)
        panel_obj._grid_dirty = True
        panel_obj.rebuild_grid()
        panel_obj.save_tab_config(tab_index)
        return

    path = panel_obj.get_tab_config_path(tab_index)
    data = {}
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                data = json.load(f) or {}
        except Exception:
            data = {}
    data.setdefault("panel", {})
    buttons = data.get("buttons") or []
    buttons.append(info)
    data["buttons"] = buttons
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def run_once(script_path):
    """Execute a downloaded script immediately, without adding a button."""
    import __main__
    src = read_script_source(script_path)
    exec(compile(src, script_path, "exec"), __main__.__dict__)


# ---------------------------------------------------------------------------
# Background workers (network I/O must never block Maya's main thread)
# ---------------------------------------------------------------------------

class _CatalogWorker(QtCore.QThread):
    done = QtCore.Signal(list, list)   # catalog, unmatched_script_names
    failed = QtCore.Signal(str)

    def run(self):
        try:
            catalog, unmatched = fetch_catalog()
        except (URLError, HTTPError) as e:
            self.failed.emit("Network error: {}".format(e))
        except Exception as e:
            self.failed.emit(str(e))
        else:
            self.done.emit(catalog, unmatched)


class _EnsureFilesWorker(QtCore.QThread):
    done = QtCore.Signal(dict, str, str)     # item, script_path, icon_path
    failed = QtCore.Signal(dict, str)

    def __init__(self, item, parent=None):
        super(_EnsureFilesWorker, self).__init__(parent)
        self.item = item

    def run(self):
        try:
            sp, ip = ensure_local_files(self.item)
        except Exception as e:
            self.failed.emit(self.item, str(e))
        else:
            self.done.emit(self.item, sp, ip or "")


class _IconsWorker(QtCore.QThread):
    """Downloads icons for a whole catalog in the background, one at a
    time, emitting iconReady as each one lands so tiles can update
    incrementally instead of waiting for the full set."""

    iconReady = QtCore.Signal(dict, str)
    iconFailed = QtCore.Signal(dict, str)
    finishedAll = QtCore.Signal()

    def __init__(self, items, parent=None):
        super(_IconsWorker, self).__init__(parent)
        self.items = list(items)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for item in self.items:
            if self._stop:
                return
            try:
                ip = ensure_icon(item)
            except Exception as e:
                if not self._stop:
                    self.iconFailed.emit(item, str(e))
                continue
            if ip and not self._stop:
                self.iconReady.emit(item, ip)
            elif not self._stop:
                self.iconFailed.emit(item, "no matching icon file in the repo")
        self.finishedAll.emit()


# ---------------------------------------------------------------------------
# UI — code viewer dialog
# ---------------------------------------------------------------------------

class _CodeViewerDialog(QtWidgets.QDialog):

    def __init__(self, title, code_text, parent=None):
        super(_CodeViewerDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 480)
        _theme.set_qss(self, "background:{bg};".format(**_C))

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        hdr = QtWidgets.QLabel(title)
        _theme.set_qss(hdr, "color:{text}; font-size:13px; font-weight:600; background:transparent;"
                           .format(**_C))
        lay.addWidget(hdr)

        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(code_text)
        _theme.set_qss(self.text_edit, """
        QPlainTextEdit {{
            background:{input}; color:{text}; border:1px solid {border};
            border-radius:6px; font-family: Consolas, "Courier New", monospace;
            font-size:11px; padding:8px;
        }}
        """.format(**_C))
        lay.addWidget(self.text_edit, 1)

        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        copy_btn = QtWidgets.QPushButton("Copy")
        close_btn = QtWidgets.QPushButton("Close")
        for b in (copy_btn, close_btn):
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setFixedHeight(28)
            _theme.set_qss(b, _SS_BTN)
        copy_btn.clicked.connect(self._copy)
        close_btn.clicked.connect(self.accept)
        row.addWidget(copy_btn)
        row.addWidget(close_btn)
        lay.addLayout(row)

    def _copy(self):
        QtWidgets.QApplication.clipboard().setText(self.text_edit.toPlainText())


# ---------------------------------------------------------------------------
# UI — "Add to Panel" picker dialog
# ---------------------------------------------------------------------------

class _AddToPanelDialog(QtWidgets.QDialog):

    def __init__(self, item_name, current_tab, parent=None):
        super(_AddToPanelDialog, self).__init__(parent)
        self.setWindowTitle("Add to Panel")
        self.setFixedSize(300, 140)
        _theme.set_qss(self, "background:{bg};".format(**_C))

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        lbl = QtWidgets.QLabel("Add \u201c{}\u201d as a button to:".format(item_name))
        lbl.setWordWrap(True)
        _theme.set_qss(lbl, "color:{text}; font-size:11px; background:transparent;".format(**_C))
        lay.addWidget(lbl)

        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(_PANEL_LABELS)
        if 0 <= current_tab < len(_PANEL_LABELS):
            self.combo.setCurrentIndex(current_tab)
        _theme.set_qss(self.combo, """
        QComboBox {{
            background:{input}; color:{text}; border:1px solid {border};
            border-radius:6px; padding:4px 8px; font-size:11px;
        }}
        """.format(**_C))
        lay.addWidget(self.combo)

        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Add")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        _theme.set_qss(ok_btn, _SS_BTN_ACCENT)
        _theme.set_qss(cancel_btn, _SS_BTN)
        for b in (ok_btn, cancel_btn):
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setFixedHeight(28)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)
        lay.addLayout(row)

    def selected_tab_index(self):
        return self.combo.currentIndex()


# ---------------------------------------------------------------------------
# UI — one grid tile
# ---------------------------------------------------------------------------

def _load_square_icon(path, size):
    """Render `path` as a crisp, exactly-square icon at `size`x`size`.

    A plain QIcon(path) leaves Qt to pick/scale a pixmap on demand, which
    is where non-square source art (and some odd-sized PNGs) end up
    blurry, off-center, or clipped inside a square QToolButton. Rendering
    it ourselves once — scale with aspect kept, then center on a
    transparent square canvas — sidesteps that entirely and matches how
    the live panel itself pre-renders icons (see sized_icon() in
    utils.py).
    """
    pm = QtGui.QPixmap(path)
    if pm.isNull():
        return None
    pm = pm.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    canvas = QtGui.QPixmap(size, size)
    canvas.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(canvas)
    painter.drawPixmap((size - pm.width()) // 2, (size - pm.height()) // 2, pm)
    painter.end()
    return QtGui.QIcon(canvas)


class _Tile(QtWidgets.QFrame):

    viewRequested = QtCore.Signal(dict)
    addRequested = QtCore.Signal(dict)
    runRequested = QtCore.Signal(dict)

    def __init__(self, item, icon_size, parent=None):
        super(_Tile, self).__init__(parent)
        self.item = item
        self._icon_path = None
        _theme.set_qss(self, """
        QFrame {{ background:{card}; border:1px solid {border}; border-radius:8px; }}
        QFrame:hover {{ border-color:{border2}; }}
        """.format(**_C))

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 6)
        lay.setSpacing(4)
        lay.setAlignment(QtCore.Qt.AlignHCenter)

        self.icon_btn = QtWidgets.QToolButton()
        self.icon_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.icon_btn.setAutoRaise(True)
        self.icon_btn.setToolTip("Downloading icon\u2026")
        # No fallback icon on purpose — an empty placeholder square until
        # the real artwork has actually downloaded reads a lot cleaner
        # than every tile briefly (or permanently, on failure) showing a
        # generic "file" glyph that looks like a mystery letter icon.
        _theme.set_qss(self.icon_btn, "QToolButton {{ background:transparent; border:1px dashed {border2}; "
            "border-radius:6px; }}".format(**_C) + _SS_TOOLTIP)
        self.icon_btn.clicked.connect(lambda: self.viewRequested.emit(self.item))
        lay.addWidget(self.icon_btn, 1, QtCore.Qt.AlignHCenter)

        self.name_lbl = QtWidgets.QLabel(item["name"])
        self.name_lbl.setAlignment(QtCore.Qt.AlignHCenter)
        self.name_lbl.setToolTip(item["name"])
        self.name_lbl.setFixedHeight(14)
        _theme.set_qss(self.name_lbl, "color:{text}; font-size:10px; background:transparent;".format(**_C)
            + _SS_TOOLTIP)
        lay.addWidget(self.name_lbl)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(4)
        self.add_btn = QtWidgets.QPushButton("Add")
        self.run_btn = QtWidgets.QPushButton("Run")
        self.add_btn.setToolTip("Add this as a button on a panel")
        self.run_btn.setToolTip("Run this script once, right now")
        _theme.set_qss(self.add_btn, _SS_BTN_ACCENT)
        _theme.set_qss(self.run_btn, _SS_BTN)
        for b in (self.add_btn, self.run_btn):
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setFixedHeight(20)
        self.add_btn.clicked.connect(lambda: self.addRequested.emit(self.item))
        self.run_btn.clicked.connect(lambda: self.runRequested.emit(self.item))
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.run_btn)
        lay.addLayout(btn_row)

        self.set_icon_size(icon_size)

    def _elide_name(self):
        fm = self.name_lbl.fontMetrics()
        elided = fm.elidedText(self.item["name"], QtCore.Qt.ElideMiddle,
                                self.width() - 12)
        self.name_lbl.setText(elided)

    def set_icon_size(self, size):
        self.icon_btn.setIconSize(QtCore.QSize(size, size))
        self.icon_btn.setFixedSize(size, size)   # stable box even with no icon yet
        # Fixed chrome above/below the icon: name row + button row + spacing
        # + margins. Using the SAME value for width and height keeps every
        # tile a true square regardless of icon size, instead of the
        # taller-than-wide rectangle a plain top-to-bottom stack gives you.
        chrome = 58
        side = max(112, size + chrome)
        self.setFixedSize(side, side)
        if self._icon_path:
            icon = _load_square_icon(self._icon_path, size)
            if icon is not None:
                self.icon_btn.setIcon(icon)
        self._elide_name()

    def set_icon(self, path):
        """Set the icon from a local file path, once it's actually been
        downloaded — rendered crisply and square at the tile's current
        icon size. Clears the dashed "waiting" placeholder border."""
        size = self.icon_btn.iconSize().width() or 48
        icon = _load_square_icon(path, size)
        if icon is None:
            return
        self._icon_path = path
        self.icon_btn.setIcon(icon)
        self.icon_btn.setToolTip("Click to view the code")
        _theme.set_qss(self.icon_btn, "QToolButton { background:transparent; border:none; }" + _SS_TOOLTIP)

    def set_busy(self, busy, text=None):
        self.add_btn.setEnabled(not busy)
        self.run_btn.setEnabled(not busy)
        if text is not None:
            self.name_lbl.setText(text)
        elif not busy:
            self._elide_name()


# ---------------------------------------------------------------------------
# UI — reflowing grid container
# ---------------------------------------------------------------------------

class _ReflowGrid(QtWidgets.QWidget):
    """A grid that keeps its column count in sync with available width /
    current tile width, so changing icon size (or resizing the dialog)
    reflows the tiles instead of leaving them a fixed column count."""

    def __init__(self, parent=None):
        super(_ReflowGrid, self).__init__(parent)
        _theme.set_qss(self, "background:transparent;")
        self._grid = QtWidgets.QGridLayout(self)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._tiles = []
        self._cols = 1

    def set_tiles(self, tiles):
        for i in reversed(range(self._grid.count())):
            item = self._grid.takeAt(i)
            w = item.widget()
            if w:
                w.setParent(None)
        self._tiles = tiles
        self._relayout(force=True)

    def resizeEvent(self, event):
        super(_ReflowGrid, self).resizeEvent(event)
        self._relayout()

    def _relayout(self, force=False):
        if not self._tiles:
            return
        tile_w = self._tiles[0].width() or self._tiles[0].sizeHint().width()
        spacing = self._grid.spacing()
        cols = max(1, (self.width() + spacing) // (tile_w + spacing))
        if cols == self._cols and not force:
            return
        self._cols = cols
        for i in reversed(range(self._grid.count())):
            self._grid.takeAt(i)
        for i, t in enumerate(self._tiles):
            r, c = divmod(i, cols)
            self._grid.addWidget(t, r, c)


# ---------------------------------------------------------------------------
# UI — top-level panel embedded as a settings tab
# ---------------------------------------------------------------------------

class FreeStuffPanel(QtWidgets.QWidget):
    """Self-contained "Free Stuff" tab body. `panel` is the live
    PhoenixPanel instance (so Add-to-Panel can write straight into its
    tab configs)."""

    def __init__(self, panel, parent=None):
        super(FreeStuffPanel, self).__init__(parent)
        self.panel = panel
        _theme.set_qss(self, "background:transparent;")

        self._catalog = []
        self._icon_size = 48
        self._catalog_worker = None
        self._icons_worker = None
        self._icon_failures = 0
        self._base_status = ""
        self._file_workers = []   # keep references so QThreads aren't GC'd
        self._pending_action = {}  # script_name -> "view"|"add"|"run"

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        hint = QtWidgets.QLabel(
            "Community scripts from the PhoenixPanel-Scripts repo. Click an "
            "icon to view its code, add it to any panel, or run it once.")
        hint.setWordWrap(True)
        _theme.set_qss(hint, "color:{hint}; font-size:10px; background:transparent;".format(**_C))
        outer.addWidget(hint)

        top_row = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.refresh_btn.setFixedHeight(26)
        _theme.set_qss(self.refresh_btn, _SS_BTN)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        self.status_lbl = QtWidgets.QLabel("")
        _theme.set_qss(self.status_lbl, "color:{hint}; font-size:10px; background:transparent;"
                                       .format(**_C))
        top_row.addWidget(self.status_lbl, 1)
        outer.addLayout(top_row)

        size_row = QtWidgets.QHBoxLayout()
        size_lbl = QtWidgets.QLabel("Icon Size")
        _theme.set_qss(size_lbl, "color:{dim}; font-size:11px; background:transparent;".format(**_C))
        size_row.addWidget(size_lbl)
        self.size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.size_slider.setRange(32, 96)
        self.size_slider.setValue(self._icon_size)
        _theme.set_qss(self.size_slider, _SS_SLIDER)
        self.size_slider.valueChanged.connect(self._on_icon_size_changed)
        size_row.addWidget(self.size_slider, 1)
        outer.addLayout(size_row)

        # No inner QScrollArea here on purpose — this widget is embedded in a
        # settings tab page that is itself already scrollable, and nesting a
        # second scroll area inside the first tends to starve this grid of
        # real vertical space (the outer scroll sizes to sizeHint). Letting
        # the outer page scroll do the work keeps one predictable scrollbar.
        self.grid = _ReflowGrid()
        outer.addWidget(self.grid, 1)

        self.refresh()

    # ------------------------------------------------------------------
    def _on_icon_size_changed(self, value):
        self._icon_size = value
        for t in self.grid._tiles:
            t.set_icon_size(value)
        self.grid._relayout(force=True)

    # ------------------------------------------------------------------
    def refresh(self):
        self.status_lbl.setText("Loading catalog\u2026")
        self.refresh_btn.setEnabled(False)
        if self._icons_worker is not None:
            self._icons_worker.stop()
        self._icon_failures = 0
        self._catalog_worker = _CatalogWorker(self)
        self._catalog_worker.done.connect(self._on_catalog_loaded)
        self._catalog_worker.failed.connect(self._on_catalog_failed)
        self._catalog_worker.start()

    def _on_catalog_loaded(self, catalog, unmatched):
        self.refresh_btn.setEnabled(True)
        self._catalog = catalog
        if not catalog:
            self.status_lbl.setText("No scripts found in the repo.")
            self.grid.set_tiles([])
            return

        base_status = "{} script(s) available.".format(len(catalog))
        if unmatched:
            base_status += " {} have no matching icon file (name must match, e.g. foo.py \u2194 foo.png).".format(
                len(unmatched))
        self.status_lbl.setText(base_status)
        self._base_status = base_status

        tiles = []
        need_download = []
        for item in catalog:
            tile = _Tile(item, self._icon_size)
            tile.viewRequested.connect(self._on_view)
            tile.addRequested.connect(self._on_add)
            tile.runRequested.connect(self._on_run)
            tiles.append(tile)
            if not self._try_set_cached_icon(tile, item):
                if item.get("icon_url"):
                    need_download.append(item)
        self.grid.set_tiles(tiles)

        # Proactively fetch every icon that isn't already cached, so tiles
        # fill in with their real artwork on their own instead of sitting
        # on the generic fallback icon until the user clicks something.
        if need_download:
            self._icons_worker = _IconsWorker(need_download, self)
            self._icons_worker.iconReady.connect(self._on_icon_downloaded)
            self._icons_worker.iconFailed.connect(self._on_icon_failed)
            self._icons_worker.start()

    def _on_catalog_failed(self, message):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText("Couldn't load the catalog: {}".format(message))

    def _on_icon_downloaded(self, item, icon_path):
        tile = self._find_tile(item)
        if tile:
            tile.set_icon(icon_path)

    def _on_icon_failed(self, item, message):
        # Swallowing this silently is exactly how "why is it still the
        # fallback icon?" happens — surface it in the status line (and
        # the Maya script console) instead.
        self._icon_failures = getattr(self, "_icon_failures", 0) + 1
        base = getattr(self, "_base_status", "")
        self.status_lbl.setText(
            "{}  ({} icon download(s) failed \u2014 see script editor)".format(
                base, self._icon_failures))
        try:
            import maya.cmds as cmds
            cmds.warning("ModPanel Free Stuff: icon for '{}' failed: {}"
                         .format(item.get("name"), message))
        except Exception:
            pass

    def _try_set_cached_icon(self, tile, item):
        """If the icon's already cached locally, show it immediately
        without kicking off a download. Returns True if it was set."""
        ip = local_icon_path(item)
        if ip and os.path.isfile(ip):
            tile.set_icon(ip)
            return True
        return False

    def _find_tile(self, item):
        for t in self.grid._tiles:
            if t.item.get("script_name") == item.get("script_name"):
                return t
        return None

    # ------------------------------------------------------------------
    def _ensure_files_then(self, item, action):
        tile = self._find_tile(item)
        if tile:
            tile.set_busy(True, "Downloading\u2026")
        worker = _EnsureFilesWorker(item, self)
        self._file_workers.append(worker)

        def _done(it, sp, ip):
            self._file_workers.remove(worker) if worker in self._file_workers else None
            t = self._find_tile(it)
            if t:
                t.set_busy(False, it["name"])
                if ip:
                    t.set_icon(ip)
            action(it, sp, ip)

        def _failed(it, message):
            self._file_workers.remove(worker) if worker in self._file_workers else None
            t = self._find_tile(it)
            if t:
                t.set_busy(False, it["name"])
            QtWidgets.QMessageBox.warning(
                self, "Free Stuff", "Couldn't download \u201c{}\u201d:\n{}"
                .format(it["name"], message))

        worker.done.connect(_done)
        worker.failed.connect(_failed)
        worker.start()

    def _on_view(self, item):
        def _show(it, sp, ip):
            src = read_script_source(sp)
            dlg = _CodeViewerDialog(it["name"], src, parent=self)
            dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        self._ensure_files_then(item, _show)

    def _on_run(self, item):
        def _run(it, sp, ip):
            try:
                run_once(sp)
            except Exception as e:
                try:
                    import maya.cmds as cmds
                    cmds.warning("ModPanel Free Stuff: {}".format(e))
                except Exception:
                    pass
                QtWidgets.QMessageBox.warning(
                    self, "Free Stuff", "Error running \u201c{}\u201d:\n{}"
                    .format(it["name"], e))
        self._ensure_files_then(item, _run)

    def _on_add(self, item):
        current_tab = getattr(self.panel, "current_tab", 0)
        dlg = _AddToPanelDialog(item["name"], current_tab, parent=self)
        result = dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        if result != QtWidgets.QDialog.Accepted:
            return
        tab_index = dlg.selected_tab_index()

        def _add(it, sp, ip):
            info = build_button_info(it, sp, ip)
            try:
                add_button_to_tab(self.panel, tab_index, info)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Free Stuff", "Couldn't add the button:\n{}".format(e))
                return
            try:
                import maya.cmds as cmds
                cmds.inViewMessage(
                    amg="Added <hl>{}</hl> to {}".format(
                        it["name"], _PANEL_LABELS[tab_index]),
                    pos="topCenter", fade=True)
            except Exception:
                pass
        self._ensure_files_then(item, _add)


# ---------------------------------------------------------------------------
# Tab-key "Free Stuff" view — data provider only.
#
# There is deliberately no separate popup/window here: PhoenixPanel itself
# (core.py's _enter_free_stuff_view / _exit_free_stuff_view) temporarily
# swaps its own buttons_data for whatever this returns and calls its
# normal rebuild_grid() — so it looks, sizes, and behaves exactly like
# Panel 1/2/3 or Q/W/E, just with a different (and non-persisted) set of
# buttons. Clicking one of these buttons runs through PhoenixPanel's own
# existing button-trigger code path, same as any real button.
# ---------------------------------------------------------------------------

_BUTTONS_DATA_CACHE = None   # last-built list, so re-entering the view is instant
_buttons_data_worker = None  # keep the QThread alive while it runs


class _CatalogAndFilesWorker(QtCore.QThread):
    """Lists the repo, makes sure every script + icon is downloaded and
    current (skipping anything already cached and unchanged), and builds
    one buttons_data-shaped dict per item. Blocking work — runs off the
    main thread; PhoenixPanel never freezes while this is going."""

    done = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def run(self):
        try:
            catalog, _unmatched = fetch_catalog()
            buttons = []
            for item in catalog:
                sp, ip = ensure_local_files(item)
                buttons.append(build_button_info(item, sp, ip))
        except Exception as e:
            self.failed.emit(str(e))
        else:
            self.done.emit(buttons)


def get_cached_buttons_data():
    """Whatever was built last time, or None if this is the first time
    the Free Stuff view has been opened this Maya session."""
    return _BUTTONS_DATA_CACHE


def request_buttons_data(callback):
    """Kick a background refresh; `callback(buttons_data)` fires on the
    main thread once it's done (and the module-level cache is updated
    first, so a later get_cached_buttons_data() sees it too)."""
    global _buttons_data_worker

    worker = _CatalogAndFilesWorker()

    def _on_done(buttons):
        global _BUTTONS_DATA_CACHE
        _BUTTONS_DATA_CACHE = buttons
        callback(buttons)

    def _on_failed(message):
        try:
            import maya.cmds as cmds
            cmds.warning("ModPanel Free Stuff: {}".format(message))
        except Exception:
            pass

    worker.done.connect(_on_done)
    worker.failed.connect(_on_failed)
    _buttons_data_worker = worker
    worker.start()
