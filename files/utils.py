# -*- coding: utf-8 -*-
"""Utility helpers for PhoenixPanel (Qt detection, config paths, icons)."""

from __future__ import annotations

import os
import sys
import html
import hashlib
import fnmatch

# ── Lazy-import flags ──────────────────────────────────────────────────────────
_MAYA_IMPORTS_LOADED = False
_QT_IMPORTS_LOADED   = False

# ── Caches ────────────────────────────────────────────────────────────────────
_ICON_CACHE      = {}
_MAX_CACHE_SIZE  = 300
_ICON_DIRS_CACHE = None   # reset by clear_icon_cache()
_MAYA_MAIN_WINDOW = None
_ICON_DATA_URI_CACHE = {}   # (icon_name, size) -> "data:image/png;base64,..." | None
_ICON_FILE_INDEX_CACHE = {} # directory -> {lowercase filename: real filename}
_RESOURCE_EXPORT_CACHE = {}  # Maya resource name -> exported local file path | None
_NATIVE_SHELF_ICON_CACHE = {}  # semantic/icon key -> QIcon | None
_RESOURCE_NAMES_CACHE = None  # [(name, lowercase name)] from resourceManager


# ── Maya / Qt lazy loaders ────────────────────────────────────────────────────

def _ensure_maya_imports():
    global _MAYA_IMPORTS_LOADED
    if not _MAYA_IMPORTS_LOADED:
        global cmds, omui, mel
        import maya.cmds as _c
        import maya.OpenMayaUI as _o
        import maya.mel as _m
        cmds = _c
        omui = _o
        mel  = _m
        _MAYA_IMPORTS_LOADED = True


def _ensure_qt_imports():
    global _QT_IMPORTS_LOADED
    if not _QT_IMPORTS_LOADED:
        global QtWidgets, QtCore, QtGui, shiboken
        try:
            from PySide6 import QtWidgets as qw, QtCore as qc, QtGui as qg
            import shiboken6 as sh
        except ImportError:
            from PySide2 import QtWidgets as qw, QtCore as qc, QtGui as qg
            import shiboken2 as sh
        QtWidgets = qw
        QtCore    = qc
        QtGui     = qg
        shiboken  = sh
        _QT_IMPORTS_LOADED = True


# ── Public helpers ────────────────────────────────────────────────────────────

def get_maya_main_window():
    global _MAYA_MAIN_WINDOW
    if _MAYA_MAIN_WINDOW is not None:
        return _MAYA_MAIN_WINDOW
    _ensure_maya_imports()
    _ensure_qt_imports()
    ptr = omui.MQtUtil.mainWindow()
    if ptr:
        _MAYA_MAIN_WINDOW = shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)
    return _MAYA_MAIN_WINDOW


def get_config_path():
    _ensure_maya_imports()
    return os.path.join(cmds.internalVar(userAppDir=True), "PhoenixPanel_config.json")


def clear_icon_cache():
    """Clear the icon cache and the icon-directory cache."""
    global _ICON_CACHE, _ICON_DIRS_CACHE, _ICON_DATA_URI_CACHE, _SIZED_ICON_CACHE
    global _ICON_FILE_INDEX_CACHE, _RESOURCE_EXPORT_CACHE, _NATIVE_SHELF_ICON_CACHE
    global _RESOURCE_NAMES_CACHE
    _ICON_CACHE.clear()
    _ICON_DATA_URI_CACHE.clear()
    _SIZED_ICON_CACHE.clear()
    _ICON_FILE_INDEX_CACHE.clear()
    _RESOURCE_EXPORT_CACHE.clear()
    _NATIVE_SHELF_ICON_CACHE.clear()
    _RESOURCE_NAMES_CACHE = None
    _ICON_DIRS_CACHE = None   # force re-scan of Maya paths on next lookup


def icon_data_uri(icon_name, size=14):
    """Resolve *icon_name* to a base64 PNG data-URI for embedding directly in
    Qt rich-text (e.g. an ``<img>`` tag inside an HTML tooltip).

    Rendering to a data-URI (rather than a plain file path) sidesteps the
    fact that many resolved icons live inside Qt resources (``:/name``) or
    Maya's resourceManager, neither of which a QToolTip's HTML engine can
    load directly. Returns None if the icon can't be resolved or rendered.
    Cached per (icon_name, size).
    """
    if not icon_name:
        return None
    key = (icon_name, size)
    if key in _ICON_DATA_URI_CACHE:
        return _ICON_DATA_URI_CACHE[key]

    _ensure_qt_imports()
    uri = None
    try:
        icon = resolve_maya_icon(icon_name)
        pm = icon.pixmap(size, size)
        if not pm.isNull():
            buf = QtCore.QBuffer()
            buf.open(QtCore.QIODevice.WriteOnly)
            pm.save(buf, "PNG")
            b64 = bytes(buf.data().toBase64()).decode("ascii")
            uri = "data:image/png;base64,{}".format(b64)
    except Exception:
        uri = None

    _ICON_DATA_URI_CACHE[key] = uri
    return uri


# ── Icon directory discovery ──────────────────────────────────────────────────

def _get_maya_icon_dirs():
    """Return a deduplicated list of every directory where Maya icons live.

    Search order (most specific first):
      1. User bitmap / icon directory
      2. User scripts directory (and its icons/ subfolder)
      3. XBMLANGPATH entries  (Maya's icon search path)
      4. MAYA_SCRIPT_PATH icons/ subfolders
      5. MAYA_MODULE_PATH icons/ subfolders
      6. Maya installation  icons/  (via MAYA_LOCATION or sys.executable)
    """
    global _ICON_DIRS_CACHE
    if _ICON_DIRS_CACHE is not None:
        return _ICON_DIRS_CACHE

    seen = set()
    dirs = []

    def _add(path):
        if not path:
            return
        raw = os.path.expandvars(os.path.expanduser(str(path)))
        raw = raw.replace("%B", "").strip().rstrip("/\\")
        if not raw:
            return
        p = os.path.normpath(raw)
        key = os.path.normcase(p)
        if key not in seen and os.path.isdir(p):
            seen.add(key)
            dirs.append(p)

    # 1 + 2 — Maya user directories
    try:
        _ensure_maya_imports()
        _add(cmds.internalVar(userBitmapsDir=True) or "")
        usr_scripts = cmds.internalVar(userScriptDir=True) or ""
        _add(usr_scripts)
        _add(os.path.join(usr_scripts, "icons"))
        _add(os.path.join(usr_scripts, "..", "icons"))   # sibling icons/ folder
    except Exception:
        pass

    # 3 — XBMLANGPATH  (semicolon on Windows, colon on Linux/Mac)
    for p in os.environ.get("XBMLANGPATH", "").split(os.pathsep):
        _add(p.strip().replace("%B", "").rstrip("/\\").strip())

    # 4 + 5 — MAYA_SCRIPT_PATH / MAYA_MODULE_PATH
    for env in ("MAYA_SCRIPT_PATH", "MAYA_MODULE_PATH"):
        for p in os.environ.get(env, "").split(os.pathsep):
            p = p.strip()
            if not p:
                continue
            _add(p)
            _add(os.path.join(p, "icons"))

    # 6 — Maya installation icons/
    maya_loc = os.environ.get("MAYA_LOCATION", "")
    if maya_loc:
        _add(os.path.join(maya_loc, "icons"))
        # Also include installed sibling Maya versions. This lets a shelf
        # configuration that still names an older built-in icon (for
        # example a Maya 2024 Sweep Mesh asset) resolve in newer Maya, and
        # provides the reverse fallback when Autodesk changed the icon
        # format/name between releases. Current-version paths still win.
        try:
            install_parent = os.path.dirname(os.path.normpath(maya_loc))
            for entry in os.listdir(install_parent):
                low = entry.lower()
                suffix = low[4:] if low.startswith("maya") else ""
                if len(suffix) == 4 and suffix.isdigit():
                    _add(os.path.join(install_parent, entry, "icons"))
        except Exception:
            pass

    # Infer from sys.executable (Maya's Python lives inside the install tree)
    try:
        exe = sys.executable or ""
        for _ in range(8):
            parent = os.path.dirname(exe)
            if not parent or parent == exe:
                break
            exe = parent
            candidate = os.path.join(exe, "icons")
            if os.path.isdir(candidate):
                _add(candidate)
                break
    except Exception:
        pass

    _ICON_DIRS_CACHE = dirs
    return dirs


# ── Icon resolution ───────────────────────────────────────────────────────────

_COMMON_ICON_EXTS = (".png", ".svg", ".xpm", ".bmp", ".jpg", ".jpeg", ".gif")


def _icon_name_candidates(icon_name):
    """Return compatible filename/resource candidates for a Maya icon.

    Some Maya shelves retain a .png name while another Maya release ships
    the same built-in image as SVG (or exposes it as an extensionless Qt
    resource). Try the stored name first, then the same stem in every common
    Maya image format.
    """
    base = os.path.basename(str(icon_name).replace("\\", "/"))
    stem, ext = os.path.splitext(base)
    out = []

    def _add(value):
        if value and value not in out:
            out.append(value)

    _add(base)
    if ext:
        _add(stem)
        for candidate_ext in _COMMON_ICON_EXTS:
            if candidate_ext.lower() != ext.lower():
                _add(stem + candidate_ext)
    else:
        for candidate_ext in _COMMON_ICON_EXTS:
            _add(base + candidate_ext)
    return out


def _find_icon_file(directory, candidates):
    """Find the first candidate in *directory*, including case-insensitive
    matching for icon packs copied from another OS or Maya release.
    """
    for name in candidates:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            return path

    index = _ICON_FILE_INDEX_CACHE.get(directory)
    if index is None:
        try:
            index = {name.lower(): name for name in os.listdir(directory)}
        except Exception:
            index = {}
        _ICON_FILE_INDEX_CACHE[directory] = index
    for name in candidates:
        actual = index.get(name.lower())
        if actual:
            path = os.path.join(directory, actual)
            if os.path.isfile(path):
                return path
    return None



def _normalise_icon_token(value):
    """Return a comparison-safe icon token with path, extension, spaces,
    punctuation and case removed.

    Maya releases do not always expose built-in shelf icons under the same
    resource filename, so comparing the semantic stem is more reliable than
    comparing the raw ``image`` string.
    """
    if not value:
        return ""
    base = os.path.basename(str(value).replace("\\", "/"))
    stem = os.path.splitext(base)[0]
    return "".join(ch.lower() for ch in stem if ch.isalnum())


def shelf_button_icon_names(control):
    """Return every image assigned to a Maya shelf button.

    Maya shelf buttons may use ``image1``, ``image2`` and ``image3`` instead
    of the simpler ``image`` flag.  The displayed image is selected by Maya
    according to the control size, so callers must retain all non-empty image
    fields rather than assuming ``image`` is authoritative.
    """
    if not control:
        return []
    try:
        _ensure_maya_imports()
    except Exception:
        return []

    out = []
    # Prefer the larger optional slots first, then fall back to image/image1.
    # All names are retained, so a release-specific missing resource can fall
    # through to another slot without changing the stored shelf command.
    for flag in ("image3", "image2", "image1", "image"):
        try:
            value = cmds.shelfButton(control, query=True, **{flag: True}) or ""
        except Exception:
            value = ""
        value = str(value).strip() if value else ""
        if value and value not in out:
            out.append(value)
    return out


def _resource_export_dir():
    """Directory used for resources that Maya can display but Qt cannot open.

    ``resourceManager -saveAs`` copies compiled Maya resources to a normal
    file.  Keeping these exports in the user's bitmap directory makes them
    stable across panel rebuilds and module reloads.
    """
    try:
        _ensure_maya_imports()
        root = cmds.internalVar(userBitmapsDir=True) or ""
    except Exception:
        root = ""
    if not root:
        root = os.path.join(os.path.expanduser("~"), ".phoenix_panel_icons")
    path = os.path.join(root, "PhoenixPanel_resource_cache")
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
    except Exception:
        return ""
    return path


def _export_maya_resource(resource_name):
    """Export a registered Maya resource to disk and return its path."""
    if not resource_name:
        return None
    key = str(resource_name)
    if key in _RESOURCE_EXPORT_CACHE:
        cached = _RESOURCE_EXPORT_CACHE[key]
        return cached if cached and os.path.isfile(cached) else None

    try:
        _ensure_maya_imports()
    except Exception:
        _RESOURCE_EXPORT_CACHE[key] = None
        return None

    folder = _resource_export_dir()
    if not folder:
        _RESOURCE_EXPORT_CACHE[key] = None
        return None

    base = os.path.basename(key.replace("\\", "/"))
    stem, ext = os.path.splitext(base)
    if not ext:
        ext = ".png"
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
    digest = hashlib.sha1(key.encode("utf-8", "ignore")).hexdigest()[:10]
    target = os.path.join(folder, "{}_{}{}".format(safe_stem or "maya_icon", digest, ext))

    if os.path.isfile(target) and os.path.getsize(target) > 0:
        _RESOURCE_EXPORT_CACHE[key] = target
        return target

    try:
        cmds.resourceManager(saveAs=(key, target))
    except Exception:
        try:
            # MEL fallback for Maya builds whose Python wrapper rejects tuple
            # arguments even though the underlying command supports saveAs.
            src = key.replace("\\", "\\\\").replace('"', '\\"')
            dst = target.replace("\\", "/").replace('"', '\\"')
            mel.eval('resourceManager -saveAs "{}" "{}"'.format(src, dst))
        except Exception:
            _RESOURCE_EXPORT_CACHE[key] = None
            return None

    if os.path.isfile(target) and os.path.getsize(target) > 0:
        _RESOURCE_EXPORT_CACHE[key] = target
        return target
    _RESOURCE_EXPORT_CACHE[key] = None
    return None


def _qicon_from_path_or_resource(value):
    """Return a usable QIcon from a path or Qt resource, else None."""
    if not value:
        return None
    _ensure_qt_imports()
    try:
        icon = QtGui.QIcon(str(value))
        if not icon.isNull() and not icon.pixmap(32, 32).isNull():
            return icon
    except Exception:
        pass
    return None


def _all_resource_names():
    """Return [(name, lowercase name), ...] for every registered Maya
    resource, cached. None when the listing is unavailable."""
    global _RESOURCE_NAMES_CACHE
    if _RESOURCE_NAMES_CACHE is not None:
        return _RESOURCE_NAMES_CACHE
    try:
        result = cmds.resourceManager(nameFilter="*") or []
    except Exception:
        return None
    if not isinstance(result, (list, tuple)):
        result = [result]
    names = []
    for name in result:
        name = str(name).strip() if name else ""
        if name:
            names.append((name, name.lower()))
    if not names:
        return None
    _RESOURCE_NAMES_CACHE = names
    return names


def _resource_matches(candidate):
    """Return registered Maya resources matching a candidate icon name."""
    try:
        _ensure_maya_imports()
    except Exception:
        return []

    candidate = str(candidate or "").strip()
    if not candidate:
        return []
    base = os.path.basename(candidate.replace("\\", "/"))
    stem = os.path.splitext(base)[0]
    queries = [base]
    if stem and stem != base:
        queries.append(stem)
    # Exact resource names differ by extension between releases.  A narrow
    # stem wildcard catches that without scanning every registered resource.
    if len(stem) >= 4:
        queries.append(stem + ".*")
        queries.append(stem + "*")

    # One full listing (~20 ms) replaces a resourceManager round-trip per
    # query (~10 ms each, ~1000 of them on a first open). Maya's nameFilter
    # is a case-insensitive glob, matched here identically and in the same
    # order.
    names = _all_resource_names()
    if names is not None:
        out = []
        for query in queries:
            q = query.lower()
            body = q[:-1] if q.endswith("*") else q
            if any(ch in body for ch in "*?["):
                match = lambda low, q=q: fnmatch.fnmatchcase(low, q)
            elif q.endswith("*"):
                match = lambda low, b=body: low.startswith(b)
            else:
                match = lambda low, b=body: low == b
            for name, low in names:
                if match(low) and name not in out:
                    out.append(name)
        return out

    out = []
    for query in queries:
        try:
            result = cmds.resourceManager(nameFilter=query) or []
        except Exception:
            try:
                safe = query.replace("\\", "\\\\").replace('"', '\\"')
                result = mel.eval('resourceManager -nameFilter "{}"'.format(safe)) or []
            except Exception:
                result = []
        if not isinstance(result, (list, tuple)):
            result = [result]
        for name in result:
            name = str(name).strip() if name else ""
            if name and name not in out:
                out.append(name)
    return out


def _resolve_icon_no_native(icon_name):
    """Resolve one icon name without the shelf-widget or grey fallback."""
    _ensure_qt_imports()
    if not icon_name:
        return None

    raw = str(icon_name)
    if os.path.exists(raw):
        icon = _qicon_from_path_or_resource(raw)
        if icon is not None:
            return icon

    base = os.path.basename(raw.replace("\\", "/"))
    candidates = _icon_name_candidates(base)

    for candidate in candidates:
        for prefix in (":/", ":/images/", ":/Icons/", ":/icons/",
                       ":/qtgradienteditor/", ":/stylesheet/"):
            icon = _qicon_from_path_or_resource(prefix + candidate)
            if icon is not None:
                return icon

    for directory in _get_maya_icon_dirs():
        path = _find_icon_file(directory, candidates)
        if path:
            icon = _qicon_from_path_or_resource(path)
            if icon is not None:
                return icon

    # Maya can render compiled resources that are not directly exposed as a
    # Qt path.  Export them to a normal file, then let QIcon load that file.
    for candidate in candidates:
        for resource_name in _resource_matches(candidate):
            for prefix in (":/", ":/images/", ":/Icons/", ":/icons/"):
                icon = _qicon_from_path_or_resource(prefix + resource_name.lstrip(":/"))
                if icon is not None:
                    return icon
            exported = _export_maya_resource(resource_name)
            if exported:
                icon = _qicon_from_path_or_resource(exported)
                if icon is not None:
                    return icon
    return None


def _icon_from_qt_shelf_widget(control):
    """Extract or capture the icon currently painted by a shelf control."""
    try:
        _ensure_maya_imports()
        _ensure_qt_imports()
    except Exception:
        return None

    names = []
    try:
        full = cmds.shelfButton(control, query=True, fullPathName=True) or ""
        if full:
            names.append(full)
    except Exception:
        pass
    names.append(control)

    ptr = None
    for name in names:
        try:
            ptr = omui.MQtUtil.findControl(name)
        except Exception:
            ptr = None
        if ptr:
            break
    if not ptr:
        return None

    try:
        widget = shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)
    except Exception:
        return None

    buttons = []
    try:
        if isinstance(widget, QtWidgets.QAbstractButton):
            buttons.append(widget)
        buttons.extend(widget.findChildren(QtWidgets.QAbstractButton))
    except Exception:
        pass
    for button in buttons:
        try:
            icon = button.icon()
            if icon is not None and not icon.isNull() and not icon.pixmap(32, 32).isNull():
                return QtGui.QIcon(icon)
        except Exception:
            continue

    labels = []
    try:
        if isinstance(widget, QtWidgets.QLabel):
            labels.append(widget)
        labels.extend(widget.findChildren(QtWidgets.QLabel))
    except Exception:
        pass
    for label in labels:
        try:
            pixmap = label.pixmap()
            if pixmap is not None and not pixmap.isNull():
                return QtGui.QIcon(pixmap)
        except Exception:
            continue

    # Last resort: capture what Maya itself is visibly painting.  This may
    # include a tiny amount of shelf background, but it is preferable to the
    # neutral grey placeholder and works even for private Autodesk widgets.
    try:
        pixmap = widget.grab()
        if pixmap is not None and not pixmap.isNull():
            return QtGui.QIcon(pixmap)
    except Exception:
        pass
    return None


def _native_shelf_button_icon(icon_names, semantic_text=""):
    """Resolve an icon from the live Maya shelf, including image1/2/image3."""
    if isinstance(icon_names, str):
        icon_names = [icon_names]
    icon_names = [str(name).strip() for name in (icon_names or []) if name]
    semantic_text = str(semantic_text or "")
    cache_semantic = "sweepmesh" if "sweepmesh" in "".join(
        ch.lower() for ch in semantic_text if ch.isalnum()) else ""
    cache_key = (tuple(icon_names), cache_semantic)
    if cache_key in _NATIVE_SHELF_ICON_CACHE:
        return _NATIVE_SHELF_ICON_CACHE[cache_key]

    try:
        _ensure_maya_imports()
        _ensure_qt_imports()
    except Exception:
        return None

    target_tokens = set()
    for value in icon_names:
        for candidate in _icon_name_candidates(value):
            token = _normalise_icon_token(candidate)
            if token:
                target_tokens.add(token)
    target_semantic = "{} {}".format(" ".join(icon_names), semantic_text).lower()
    target_compact = "".join(ch for ch in target_semantic if ch.isalnum())
    sweep_target = "sweepmesh" in target_compact or (
        "sweep" in target_semantic and "mesh" in target_semantic)

    try:
        shelf_root = "ShelfLayout"
        if not cmds.shelfTabLayout(shelf_root, exists=True):
            try:
                shelf_root = mel.eval("$tmp = $gShelfTopLevel") or ""
            except Exception:
                shelf_root = ""
        if not shelf_root or not cmds.shelfTabLayout(shelf_root, exists=True):
            return None
        shelves = cmds.shelfTabLayout(shelf_root, query=True, childArray=True) or []
    except Exception:
        return None

    for shelf in shelves:
        try:
            buttons = cmds.shelfLayout(shelf, query=True, childArray=True) or []
        except Exception:
            continue
        for button in buttons:
            full = button if "|" in str(button) else "{}|{}".format(shelf, button)
            control = full if cmds.shelfButton(full, exists=True) else button
            if not cmds.shelfButton(control, exists=True):
                continue

            images = shelf_button_icon_names(control)
            image_tokens = {_normalise_icon_token(name) for name in images if name}
            matched = bool(target_tokens.intersection(image_tokens))

            label = annotation = command = ""
            if not matched or sweep_target:
                try:
                    label = cmds.shelfButton(control, query=True, label=True) or ""
                    annotation = cmds.shelfButton(control, query=True, annotation=True) or ""
                    command = cmds.shelfButton(control, query=True, command=True) or ""
                except Exception:
                    pass
                button_semantic = "{} {} {} {}".format(
                    " ".join(images), label, annotation, command).lower()
                button_compact = "".join(ch for ch in button_semantic if ch.isalnum())
                if sweep_target and (
                    "sweepmesh" in button_compact or
                    ("sweep" in button_semantic and "mesh" in button_semantic)
                ):
                    matched = True

            if not matched:
                continue

            # The crucial Maya-2024 path: image1/image2/image3 can contain the
            # real resource even when the simpler image query does not.
            for image_name in images:
                icon = _resolve_icon_no_native(image_name)
                if icon is not None:
                    _NATIVE_SHELF_ICON_CACHE[cache_key] = icon
                    return icon

            icon = _icon_from_qt_shelf_widget(control)
            if icon is not None and not icon.isNull():
                _NATIVE_SHELF_ICON_CACHE[cache_key] = icon
                return icon

    _NATIVE_SHELF_ICON_CACHE[cache_key] = None
    return None

def _fallback_icon():
    """Return (and cache) a neutral placeholder QIcon."""
    _ensure_qt_imports()
    if "__fallback__" in _ICON_CACHE:
        return _ICON_CACHE["__fallback__"]
    pm = QtGui.QPixmap(32, 32)
    from . import theme as _theme
    pm.fill(_theme.qcol("#50586b"))
    icon = QtGui.QIcon(pm)
    _ICON_CACHE["__fallback__"] = icon
    return icon


def _pixmap_from_path(path):
    """Load a QPixmap from an absolute path, preserving transparency."""
    _ensure_qt_imports()
    pm = QtGui.QPixmap(path)
    return pm if not pm.isNull() else None


def _resolve_icon_uncached(icon_name, semantic_text=""):
    """Resolve one Maya icon, only using the grey placeholder at the end."""
    icon = _resolve_icon_no_native(icon_name)
    if icon is not None:
        return icon

    native_icon = _native_shelf_button_icon([icon_name], semantic_text=semantic_text)
    if native_icon is not None and not native_icon.isNull():
        return native_icon
    return _fallback_icon()


def resolve_maya_icon_candidates(icon_names, semantic_text=""):
    """Resolve the first usable icon from several Maya shelf image fields.

    ``semantic_text`` is only used for the final live-shelf fallback.  It lets
    an older saved button whose ``image`` value is generic still locate the
    Maya 2024 Sweep Mesh shelf control through its label/annotation/command.
    """
    if isinstance(icon_names, str):
        icon_names = [icon_names]
    names = []
    for name in icon_names or []:
        name = str(name).strip() if name else ""
        if name and name not in names:
            names.append(name)

    semantic_compact = "".join(ch.lower() for ch in str(semantic_text or "") if ch.isalnum())
    cache_key = ("__candidates__", tuple(names), "sweepmesh" if "sweepmesh" in semantic_compact else "")
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    for name in names:
        icon = _resolve_icon_no_native(name)
        if icon is not None:
            _ICON_CACHE[cache_key] = icon
            return icon

    native = _native_shelf_button_icon(names, semantic_text=semantic_text)
    if native is not None and not native.isNull():
        _ICON_CACHE[cache_key] = native
        return native

    icon = _fallback_icon()
    _ICON_CACHE[cache_key] = icon
    return icon


def resolve_maya_icon(icon_name):
    """Resolve a Maya shelf icon name or path to a QIcon (cached)."""
    if icon_name in _ICON_CACHE:
        return _ICON_CACHE[icon_name]

    if len(_ICON_CACHE) > _MAX_CACHE_SIZE:
        keys = list(_ICON_CACHE.keys())
        for key in keys[:len(keys) // 2]:
            if key != "__fallback__":
                _ICON_CACHE.pop(key, None)

    icon = resolve_maya_icon_candidates([icon_name])
    _ICON_CACHE[icon_name] = icon
    return icon


_SIZED_ICON_CACHE = {}   # (icon_name, size) -> QIcon


def sized_icon_candidates(icon_names, size, semantic_text=""):
    """Sized variant of :func:`resolve_maya_icon_candidates`."""
    if isinstance(icon_names, str):
        icon_names = [icon_names]
    names = tuple(str(name).strip() for name in (icon_names or []) if name)
    semantic_compact = "".join(ch.lower() for ch in str(semantic_text or "") if ch.isalnum())
    key = ("__candidate_size__", names, int(size),
           "sweepmesh" if "sweepmesh" in semantic_compact else "")
    if key in _SIZED_ICON_CACHE:
        return _SIZED_ICON_CACHE[key]

    _ensure_qt_imports()
    icon = resolve_maya_icon_candidates(names, semantic_text=semantic_text)
    try:
        pixmap = icon.pixmap(int(size), int(size))
        if pixmap.isNull():
            result = icon
        else:
            if pixmap.width() != int(size) or pixmap.height() != int(size):
                pixmap = pixmap.scaled(int(size), int(size), QtCore.Qt.KeepAspectRatio,
                                       QtCore.Qt.SmoothTransformation)
            result = QtGui.QIcon(pixmap)
    except Exception:
        result = icon
    _SIZED_ICON_CACHE[key] = result
    return result


def sized_icon(icon_name, size):
    """Resolve `icon_name` via resolve_maya_icon() and force-render it to an
    exact `size` x `size` pixmap, wrapped in a fresh QIcon.

    Needed because some Maya-native icons — particularly ones resolved
    through Qt's own compiled-in resource system (":/name") rather than a
    plain file on disk — carry an internal notion of their "natural" size
    that Qt's icon engine can be conservative about scaling up past, even
    though QToolButton.setIconSize() asks for a specific size. Rendering the
    pixmap ourselves at the exact target size sidesteps that entirely:
    whatever we hand back is only ever square pixels of that dimension.

    Cached per (icon_name, size) since this gets called on every grid
    rebuild / hot-button refresh, potentially at several different sizes
    across the session (panel_scale changing, pie items, etc.).
    """
    if size <= 0 or not icon_name:
        return resolve_maya_icon(icon_name)

    key = (icon_name, int(size))
    if key in _SIZED_ICON_CACHE:
        return _SIZED_ICON_CACHE[key]

    if len(_SIZED_ICON_CACHE) > _MAX_CACHE_SIZE:
        keys = list(_SIZED_ICON_CACHE.keys())
        for k in keys[:len(keys) // 2]:
            del _SIZED_ICON_CACHE[k]

    _ensure_qt_imports()
    icon = resolve_maya_icon(icon_name)
    try:
        pm = icon.pixmap(size, size)
        if pm.isNull():
            result = icon
        else:
            if pm.width() != size or pm.height() != size:
                pm = pm.scaled(size, size, QtCore.Qt.KeepAspectRatio,
                                QtCore.Qt.SmoothTransformation)
            result = QtGui.QIcon(pm)
    except Exception:
        result = icon

    _SIZED_ICON_CACHE[key] = result
    return result


# ── Rich tooltip builder (main command + pie-menu preview) ───────────────────

def _tip_img_html(uri):
    if not uri:
        return ""
    return ('<img src="{}" width="14" height="14" '
            'style="vertical-align:middle;margin-right:4px;">').format(uri)


def build_pie_tooltip_html(main_name, main_tip, main_icon_uri, pie_entries):
    """Compose the rich HTML tooltip for a button that has pie commands
    configured. Shown while the pie is closed (plain hover).

    ``pie_entries`` is a list of ``(icon_data_uri_or_None, label_text)``
    tuples, one per configured pie slot (already trimmed to <= 6 and in
    clockwise order). Returns an ``<html>``-wrapped string ready to hand
    straight to ``QWidget.setToolTip()`` — Qt only auto-detects rich text
    when the string *starts* with a tag, so the wrapper is required, not
    cosmetic.
    """
    lines = []
    lines.append("<b>Main:</b>")
    lines.append("{}{}".format(_tip_img_html(main_icon_uri),
                                html.escape(main_name or "Button")))
    if main_tip:
        lines.append(html.escape(main_tip))

    if pie_entries:
        lines.append("")
        lines.append("<b>Hold Left Click:</b>")
        for uri, label in pie_entries:
            lines.append("{}{}".format(_tip_img_html(uri),
                                        html.escape(label or "Command")))

    return "<html>{}</html>".format("<br>".join(lines))


def compute_pie_dim_rect(panel, mode):
    """Screen-space rect to dim behind an open pie menu.

    mode == "panel"  -> just the panel's own geometry.
    mode == "screen" -> Maya's main window (frameGeometry, so it covers the
                        whole application including its own frame/borders),
                        falling back to the screen containing the panel if
                        the main window can't be resolved for some reason.

    Returns None if nothing usable could be determined — callers should
    treat that as "don't show a dim overlay this time" rather than error.
    """
    _ensure_qt_imports()

    if mode != "screen":
        try:
            return panel.geometry()
        except Exception:
            return None

    try:
        main_win = get_maya_main_window()
        if main_win is not None:
            return main_win.frameGeometry()
    except Exception:
        pass

    try:
        center = panel.geometry().center()
        screen = QtWidgets.QApplication.screenAt(center)
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            return screen.geometry()
    except Exception:
        pass
    return None


# ── Settings wheel guard ──────────────────────────────────────────────────────
# Scrolling the mouse wheel over a spin box or combo box in a settings window
# scrolls the page instead of changing the value. Sliders keep their normal
# wheel behaviour, so a value only changes on wheel when the cursor is on a
# slider.
_WHEEL_GUARD_PROP = "_modpanel_wheel_guard"


def install_wheel_guard(window):
    """Apply the wheel guard to every spin box / combo box inside ``window``
    (including ones created later)."""
    _ensure_qt_imports()
    window.setProperty(_WHEEL_GUARD_PROP, True)
    app = QtWidgets.QApplication.instance()
    if app is None or getattr(app, "_modpanel_wheel_guard", None) is not None:
        return

    class _WheelGuard(QtCore.QObject):
        def eventFilter(self, obj, event):
            try:
                if event.type() != QtCore.QEvent.Wheel:
                    return False
                if not isinstance(obj, (QtWidgets.QAbstractSpinBox,
                                        QtWidgets.QComboBox)):
                    return False
                if not obj.window().property(_WHEEL_GUARD_PROP):
                    return False
                parent = obj.parentWidget()
                while parent is not None and not isinstance(
                        parent, QtWidgets.QAbstractScrollArea):
                    parent = parent.parentWidget()
                if parent is not None:
                    QtCore.QCoreApplication.sendEvent(parent.viewport(), event)
                return True
            except Exception:
                return False

    guard = _WheelGuard(app)
    app._modpanel_wheel_guard = guard
    app.installEventFilter(guard)
