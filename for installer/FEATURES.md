# ModPanel features

## Panel

- Floating, frameless panel that opens under the mouse cursor.
- **Pin** (`◎`) keeps it open and lets you drag it around by the title. Unpinned, it closes when you click outside it or press `Escape`.
- **Close on click**: running a command closes the panel. Each button and hot button can invert this individually.
- Stays above Maya without covering other applications.
- Resizes itself to fit its content.

## Panels and tabs

- Three main panels plus three hidden panels, each with its own buttons.
  - `1` `2` `3` switch main panels; `Q` `W` `E` open the hidden panels.
  - Right-click the title cycles the main panels.
  - Thin colored indicators under the title show the active panel (blue, green, orange).
- **Auto-switching**:
  - Panel 2 activates when a chosen workspace (default *UV Editing*) is active.
  - Panel 3 activates when the cursor is over Hypershade, or (optional) when shader/material nodes are selected.

## Buttons

- Grid of icon buttons with optional text label overlays.
- **Left-click** runs the command (MEL or Python).
- **Middle-click** runs the button's secondary command.
- **Right-click menu**: Edit Label, Choose from Shelf, Choose Local File (icon), Clear Icon, Edit Pie Commands, Add to Another Button's Pie, Reposition, Delete.
- **Reposition mode**: drag buttons to reorder them.
- Add buttons with **+ Shelf** (pick from any Maya shelf) or by middle-dragging a Maya shelf button onto a pinned panel.
- Grid columns, button scale, spacing and full/partial row alignment are adjustable.

## Pie menus

- Hold left-click on a button or hot button to open a radial pie of up to 6 commands; release over an item to run it.
- Per-button start angle, adjustable hold delay and icon scale.
- Optional background dimming (panel or whole screen) with delay, fade speed and darkness settings.
- Pie editor with icons, tooltips, MEL/Python and a Test button.

## Hot buttons (title bar)

- Up to 10 icon buttons in the title bar, shared across all panels.
- Each has a left-click command, optional right-click command, pie menu, icon, tooltip and close-on-click override.
- Reorderable; adjustable gap and icon scale.

## Title bar actions

- **Middle-click** the title: runs a custom command (none by default).
- **Right-click** the title: switches panel, or runs a custom command.
- **Double-click** the title: hot-reloads ModPanel, or runs a custom command.
- **Right-click `+ Shelf`**: toggles *Use Default Material*.
- **Right-click `⚙`**: toggles between two chosen workspaces (default *General* ⇄ *UV Editing*).

## Search and recent commands

- `X` shows a search bar that filters buttons as you type (`Escape` hides it), or keep it always visible.
- Optional **recent commands** row showing the last 5 buttons you ran.

## Free Stuff

- `Tab` (or Settings → Free Stuff) opens a catalog of community scripts from the PhoenixPanel-Scripts GitHub repo.
- View a script's source, **Run Once**, or **Add to Panel** as a button on any panel. Added buttons link to the downloaded file, so updates are picked up automatically.

## Look and styles

- **UI Style presets**, switched instantly from Settings → Look:
  - **ModPanel (Dark)**: default. Black surfaces, thin outlines, `#46b6ff` accent, outlined primary buttons, small corner radii.
  - **Classic (PhoenixPanel)**: the original navy palette.
- Custom colors for background, border, title bar, button, hover, pressed, selected, text, icon and accent.
- Opacity, border thickness, corner radius, button padding, button spacing, visual scale and title text.
- Import/export Look files; reset to the active style's defaults.

## Settings window

Pages: **Layout**, **Buttons**, **Title**, **Workspaces**, **Look**, **Data**, **Free Stuff**, **Credits**.

- **Layout**: panel scale, grid, alignment, hot-button spacing, pie behavior, input options.
- **Buttons**: hot-button editor (visibility, name, tooltip, code, right-click code, pies, icons).
- **Title**: title text and title click actions.
- **Workspaces**: gear toggle pair and auto-switch workspace.
- **Data**: export/import full presets (panels, hot buttons, title actions, look) with selective import; delete all buttons on the current panel.

## Input

- Open from a shelf button or hotkey (`open_phoenix_panel.py`).
- Startup loader (`loader.py`) for `userSetup.py`.

## Data and safety

- All settings saved automatically to JSON in the Maya user folder.
- Existing PhoenixPanel configs load unchanged; untouched classic Look values migrate to ModPanel automatically while customized values are kept.
- Malformed or hand-edited config values fall back safely instead of breaking the panel.
