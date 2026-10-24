# -*- coding: utf-8 -*-
"""Dialog for picking existing shelf buttons to add into PhoenixPanel."""

from __future__ import annotations

import maya.cmds as cmds
import maya.mel as mel

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

from .utils import (resolve_maya_icon, resolve_maya_icon_candidates,
                    shelf_button_icon_names)


class ShelfPickerDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(ShelfPickerDialog, self).__init__(parent)

        self.setWindowTitle("Select Shelf Buttons")
        self.resize(420, 520)

        self._data = []
        self._process_queue = []
        self._process_index = 0
        self._current_shelf = ""
        self._icon_load_index = 0
        self._is_closed = False  # Track if dialog was closed

        layout = QtWidgets.QVBoxLayout(self)

        # Shelf selector row
        row = QtWidgets.QHBoxLayout()
        self.shelf_combo = QtWidgets.QComboBox()
        self.refresh_btn = QtWidgets.QPushButton("Refresh")

        row.addWidget(QtWidgets.QLabel("Shelf:"))
        row.addWidget(self.shelf_combo, 1)
        row.addWidget(self.refresh_btn)
        layout.addLayout(row)

        # List of shelf buttons
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self.list_widget)

        # Footer buttons
        row2 = QtWidgets.QHBoxLayout()
        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.ok_btn = QtWidgets.QPushButton("OK")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")

        row2.addWidget(self.select_all_btn)
        row2.addStretch(1)
        row2.addWidget(self.ok_btn)
        row2.addWidget(self.cancel_btn)
        layout.addLayout(row2)

        # Signals
        self.refresh_btn.clicked.connect(self._refresh_all_shelves)
        self.refresh_btn.setToolTip("Load all Maya shelves then refresh this list")
        self.shelf_combo.currentIndexChanged.connect(self.populate_buttons)
        self.select_all_btn.clicked.connect(self.list_widget.selectAll)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        # Start
        self.populate_shelves()

    # ---------------------------------------------------------
    # REFRESH — activate every shelf to force icon load
    # ---------------------------------------------------------
    def _refresh_all_shelves(self):
        """Activate every Maya shelf tab once so their icons initialise,
        then restore the originally active shelf and repopulate this picker.
        """
        try:
            shelf_top_level = mel.eval("$temp = $gShelfTopLevel")

            if not shelf_top_level or not cmds.shelfTabLayout(
                shelf_top_level, exists=True
            ):
                cmds.warning("Could not find Maya's main shelf tab layout.")
                self.populate_shelves()
                return

            original_shelf = cmds.shelfTabLayout(
                shelf_top_level, query=True, selectTab=True
            )

            shelf_tabs = cmds.shelfTabLayout(
                shelf_top_level, query=True, childArray=True
            ) or []

            if not shelf_tabs:
                cmds.warning("No Maya shelves were found.")
                self.populate_shelves()
                return

            for shelf in shelf_tabs:
                if not cmds.control(shelf, exists=True):
                    continue
                try:
                    cmds.shelfTabLayout(
                        shelf_top_level, edit=True, selectTab=shelf
                    )
                    cmds.refresh(force=True)
                    cmds.evalDeferred(lambda: None)
                except Exception as shelf_err:
                    cmds.warning(
                        "Could not load shelf '{}': {}".format(shelf, shelf_err)
                    )

            if original_shelf and cmds.control(original_shelf, exists=True):
                cmds.shelfTabLayout(
                    shelf_top_level, edit=True, selectTab=original_shelf
                )
                cmds.refresh(force=True)

        except Exception as e:
            cmds.warning("ModPanel: shelf refresh error: {}".format(e))

        self.populate_shelves()

    # ---------------------------------------------------------
    # GET SHELVES
    # ---------------------------------------------------------
    def get_shelves(self):
        if cmds.shelfTabLayout("ShelfLayout", exists=True):
            try:
                return cmds.shelfTabLayout("ShelfLayout", q=True, childArray=True) or []
            except Exception:
                return []
        return []

    # ---------------------------------------------------------
    # POPULATE SHELF LIST
    # ---------------------------------------------------------
    def populate_shelves(self):
        self.shelf_combo.blockSignals(True)
        self.shelf_combo.clear()

        shelves = self.get_shelves()
        for s in shelves:
            self.shelf_combo.addItem(s)

        self.shelf_combo.blockSignals(False)

        if shelves:
            self.populate_buttons()

    # ---------------------------------------------------------
    # POPULATE BUTTONS (ASYNC)
    # ---------------------------------------------------------
    def populate_buttons(self):
        self.list_widget.clear()
        self._data = []
        self._icon_load_index = 0

        shelf = self.shelf_combo.currentText()
        if not shelf:
            return

        self._current_shelf = shelf

        try:
            children = cmds.shelfLayout(shelf, q=True, childArray=True) or []
        except Exception:
            children = []

        # Start async processing
        self._process_queue = list(children)
        self._process_index = 0
        
        if self._process_queue:
            QtCore.QTimer.singleShot(0, self._process_next_batch)

    # ---------------------------------------------------------
    # PROCESS BUTTONS IN BATCHES
    # ---------------------------------------------------------
    def _process_next_batch(self):
        # Safety check - stop if dialog was closed
        if self._is_closed:
            return
        
        BATCH_SIZE = 20  # Process 20 buttons at a time
        
        shelf = self._current_shelf
        
        for _ in range(BATCH_SIZE):
            if self._process_index >= len(self._process_queue):
                # Done processing, start loading icons
                QtCore.QTimer.singleShot(0, self._load_icons_batch)
                return
            
            btn = self._process_queue[self._process_index]
            self._process_index += 1
            
            # Build full path
            full = f"{shelf}|{btn}"
            if not cmds.shelfButton(full, exists=True):
                if not cmds.shelfButton(btn, exists=True):
                    continue
                full = btn

            # Extract fields
            try:
                label       = cmds.shelfButton(full, q=True, label=True) or ""
                ann         = cmds.shelfButton(full, q=True, annotation=True) or ""
                icon_label  = cmds.shelfButton(full, q=True, imageOverlayLabel=True) or ""
                icon_candidates = shelf_button_icon_names(full)
                icon        = icon_candidates[0] if icon_candidates else ""
                cmd         = cmds.shelfButton(full, q=True, command=True) or ""
                src         = cmds.shelfButton(full, q=True, sourceType=True) or "mel"
                dbl_cmd     = cmds.shelfButton(full, q=True, doubleClickCommand=True) or ""
            except Exception:
                continue

            # STRICT RULE: overlay ONLY from imageOverlayLabel
            if icon_label and icon_label.strip():
                overlay = icon_label.strip()
            else:
                overlay = ""

            # Safety cleanup
            if overlay.lower() in {"-imageoverlaylabel", "imageoverlaylabel"}:
                overlay = ""

            info = {
                "full_path": full,
                "label": overlay,
                "name": label.strip() if label else "",
                "annotation": ann,
                "icon_label": icon_label,
                "icon": icon,
                "icon_candidates": icon_candidates,
                "command": cmd,
                "sourceType": src,
                "doubleClickCommand": dbl_cmd,
                "doubleClickSourceType": src,   # dbl-click shares the same language
            }
            self._data.append(info)

            # Determine display name ONLY from the shelf's label
            if label and label.strip():
                display = label.strip()
            else:
                display = "The button has no name"

            item = QtWidgets.QListWidgetItem(display)
            
            # Store the data index; icon loading needs all image1/2/3 values
            # plus the command metadata for Maya-2024 built-in fallbacks.
            item.setData(QtCore.Qt.UserRole, len(self._data) - 1)
            
            if ann:
                item.setToolTip(ann)

            self.list_widget.addItem(item)
        
        # Schedule next batch if there are more items
        if self._process_index < len(self._process_queue):
            QtCore.QTimer.singleShot(0, self._process_next_batch)

    # ---------------------------------------------------------
    # LOAD ICONS IN BATCHES (ASYNC)
    # ---------------------------------------------------------
    def _load_icons_batch(self):
        # Safety check - stop if dialog was closed
        if self._is_closed:
            return
        
        BATCH_SIZE = 10  # Load 10 icons at a time
        
        count = self.list_widget.count()
        
        for _ in range(BATCH_SIZE):
            if self._icon_load_index >= count:
                return  # Done loading icons
            
            item = self.list_widget.item(self._icon_load_index)
            if item is None:  # Safety check
                self._icon_load_index += 1
                continue
            
            data_index = item.data(QtCore.Qt.UserRole)
            try:
                info = self._data[int(data_index)]
            except Exception:
                info = {}

            icon_names = info.get("icon_candidates") or [info.get("icon", "")]
            semantic = "{} {} {} {}".format(
                info.get("name", ""), info.get("label", ""),
                info.get("annotation", ""), info.get("command", ""))
            if any(icon_names):
                try:
                    item.setIcon(resolve_maya_icon_candidates(icon_names, semantic))
                except Exception:
                    pass
            
            self._icon_load_index += 1
        
        # Schedule next batch if there are more icons to load
        if self._icon_load_index < count:
            QtCore.QTimer.singleShot(0, self._load_icons_batch)

    # ---------------------------------------------------------
    # CLEANUP
    # ---------------------------------------------------------
    def closeEvent(self, event):
        """Clean up when dialog closes."""
        self._is_closed = True
        self._process_queue.clear()
        self._data.clear()
        super(ShelfPickerDialog, self).closeEvent(event)

    def reject(self):
        """Override reject to ensure cleanup."""
        self._is_closed = True
        super(ShelfPickerDialog, self).reject()

    def accept(self):
        """Override accept to ensure cleanup."""
        self._is_closed = True
        super(ShelfPickerDialog, self).accept()

    # ---------------------------------------------------------
    # GET SELECTED BUTTONS
    # ---------------------------------------------------------
    def selected_buttons(self):
        out = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.isSelected():
                if i < len(self._data):
                    out.append(self._data[i])
        return out