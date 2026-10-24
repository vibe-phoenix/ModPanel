# ModPanel

A fast, floating custom shelf for Autodesk Maya. ModPanel pops up under your cursor with your own buttons, hold-to-open pie menus, hot buttons, search and per-workspace panels, then gets out of the way.

It defaults to the dark **ModPanel** style (black surfaces, thin outlines, blue accent, slightly rounded corners). The original **Classic (PhoenixPanel)** style is one click away in Settings.

See [FEATURES.md](FEATURES.md) for the full feature list.

---

## Requirements

- Autodesk Maya 2024 or newer (PySide2 or PySide6)
- Windows (tested on Maya 2027)

## Installation

1. Copy the `phoenix_panel` folder into your Maya scripts folder, for example:

   ```
   Documents\maya\2027\scripts\phoenix_panel
   ```

2. Open ModPanel from the Script Editor (Python tab), a shelf button or a hotkey:

   ```python
   import phoenix_panel
   phoenix_panel.open_phoenix_panel()
   ```

   `open_phoenix_panel.py` contains the same snippet, ready to drag onto a shelf.

### Load at startup

Add this to `Documents\maya\2027\scripts\userSetup.py` (create the file if it doesn't exist):

```python
try:
    from phoenix_panel import loader
    loader.load()
except Exception as e:
    print("ModPanel loader error: {}".format(e))
```

`loader.py` waits until Maya's UI is ready, then preloads ModPanel in the background: the panel is built hidden and all button, hot-button and pie icons are resolved ahead of time, so the very first open is instant. To also open the panel as soon as Maya starts, set `OPEN_ON_STARTUP = True` at the top of `loader.py`.

## Quick start

| Action | How |
|---|---|
| Open the panel | Shelf button or hotkey running `open_phoenix_panel()` |
| Run a button | Left-click |
| Open a button's pie menu | Hold left-click |
| Run a button's secondary command | Middle-click |
| Edit a button | Right-click it |
| Add shelf buttons | `+ Shelf`, or middle-drag a Maya shelf button onto a pinned panel |
| Switch panels | `1` `2` `3`, hidden panels `Q` `W` `E`, or right-click the title |
| Search | `X` (Escape hides it) |
| Free Stuff catalog | `Tab` |
| Settings | `⚙` button |
| Close | `Escape` (unpinned) |

## Changing the style

Settings → **Look** → **UI Style**:

- **ModPanel (Dark)**: the default.
- **Classic (PhoenixPanel)**: the original navy palette.

The switch applies instantly to the panel, settings and every ModPanel window, and is remembered. Colors, corner radius, opacity, padding and scale can be fine-tuned in the same tab.

## Window behavior

ModPanel and its windows stay above Maya, not above other applications.

## Configuration files

Settings are saved as JSON in your Maya user folder (`Documents\maya\`):

| File | Contents |
|---|---|
| `PhoenixPanel_config_global.json` | Shared settings, hot buttons, Look, UI style, recent commands |
| `PhoenixPanel_config_tab<N>.json` | Buttons for each panel |

The file names are kept from PhoenixPanel so existing setups load without changes. Use Settings → **Data** to export or import everything as one preset file.

## Package layout

| File | Purpose |
|---|---|
| `__init__.py` | Package entry, exposes `open_phoenix_panel()` |
| `launcher.py` | Opens the panel |
| `loader.py` | Startup loader for `userSetup.py` |
| `core.py` | Main panel window |
| `widgets.py` | Panel buttons and pie menus |
| `settings.py` | Settings window |
| `theme.py` | UI style presets (ModPanel / Classic) |
| `pie_editor.py` | Pie command editor |
| `shelf_picker.py` | Pick buttons from Maya shelves |
| `free_stuff.py` | Community scripts browser |
| `utils.py` | Config paths, icon lookup, helpers |
| `open_phoenix_panel.py` | Shelf/hotkey launcher snippet |

## Reloading

Double-click the panel title to hot-reload every ModPanel module (unless a custom double-click command is set).
