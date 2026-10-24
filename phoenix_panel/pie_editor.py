# -*- coding: utf-8 -*-
"""Compact 'Edit Pie Commands' dialog.

Opened directly from a button's context menu ("Edit Pie Commands") instead
of the full Settings window, so tweaking a pie doesn't require navigating
to Settings and finding the right tab. Works identically for regular panel
buttons and the 10 title-bar hot buttons — the caller supplies a getter and
a setter for that button's ``pie_commands`` list plus a display title.
"""

from __future__ import annotations

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from . import theme as _theme

MAX_PIE_COMMANDS = 6

_SLOT_POSITIONS = [
    "Top", "Upper-right", "Lower-right", "Bottom", "Lower-left", "Upper-left",
]

_SS_INPUT = """
QLineEdit, QTextEdit, QComboBox {
    background: #14161f; color: #dfe3ff; border: 1px solid #2c3348;
    border-radius: 4px; padding: 3px 6px; font-size: 11px;
}
QComboBox::drop-down { border: none; }
"""
_SS_BTN = """
QPushButton {
    background: #252a39; color: #c8d2ff; border: 1px solid #3a4060;
    border-radius: 4px; padding: 3px 10px; font-size: 10px;
}
QPushButton:hover { background: #2e3448; }
"""

# Module-level "clipboard" for the per-slot Copy/Paste buttons.
_SLOT_CLIPBOARD = None


def _empty_slot():
    return {"name": "", "tooltip": "", "type": "mel", "code": "", "icon": "",
            "icon_candidates": []}


class PieCommandEditorDialog(QtWidgets.QDialog):
    """Edits up to MAX_PIE_COMMANDS pie-command slots for one button.

    get_pies():        () -> list[dict]      current pie_commands (unsanitized ok)
    set_pies(list):     persists the new list AND refreshes the live button
                         (tooltip / provider already reads live, so nothing
                         else needs to change).
    icon_resolver(name): -> QIcon, for the preview label
    """

    def __init__(self, parent, title, get_pies, set_pies, icon_resolver=None,
                 get_angle=None, set_angle=None):
        super(PieCommandEditorDialog, self).__init__(parent)
        from .utils import install_wheel_guard
        install_wheel_guard(self)
        self.setWindowTitle(title)
        self.resize(480, 460)
        _theme.set_qss(self, "background:#1b1e29;")

        self._set_pies      = set_pies
        self._get_angle      = get_angle
        self._set_angle      = set_angle
        self._icon_resolver  = icon_resolver
        self._icon_names     = []   # one per slot, kept in sync with UI
        self._icon_candidates = []  # Maya image1/image2/image3 names per slot

        raw = get_pies() or []
        slots = [dict(s) for s in raw[:MAX_PIE_COMMANDS] if isinstance(s, dict)]
        while len(slots) < MAX_PIE_COMMANDS:
            slots.append(_empty_slot())

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)

        hint = QtWidgets.QLabel(
            "Up to 6 commands, shown clockwise starting from the top. "
            "Empty slots (no code) are skipped when the pie opens.")
        hint.setWordWrap(True)
        _theme.set_qss(hint, "color:#8894c0; font-size:10px;")
        lay.addWidget(hint)

        if self._get_angle is not None and self._set_angle is not None:
            lay.addLayout(self._build_rotation_row(self._get_angle()))

        self.tabs = QtWidgets.QTabWidget()
        lay.addWidget(self.tabs, 1)

        self._name_edits  = []
        self._tip_edits   = []
        self._type_boxes  = []
        self._code_edits  = []
        self._icon_lbls   = []

        for i in range(MAX_PIE_COMMANDS):
            self._icon_names.append(slots[i].get("icon", ""))
            raw_candidates = slots[i].get("icon_candidates", [])
            self._icon_candidates.append(
                list(raw_candidates) if isinstance(raw_candidates, (list, tuple)) else [])
            self.tabs.addTab(self._build_slot_tab(i, slots[i]),
                              "{}".format(i + 1))

        btn_row = QtWidgets.QHBoxLayout()
        ok_btn     = QtWidgets.QPushButton("Save")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        _theme.set_qss(ok_btn, _SS_BTN)
        _theme.set_qss(cancel_btn, _SS_BTN)
        ok_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

    # ------------------------------------------------------------ slot UI
    # ------------------------------------------------------------ rotation
    def _build_rotation_row(self, current_angle):
        row = QtWidgets.QVBoxLayout()
        row.setSpacing(4)

        self._angle_check = QtWidgets.QCheckBox("Override this button's rotation")
        _theme.set_qss(self._angle_check, "color:#c8d2ff; font-size:10px;")
        row.addWidget(self._angle_check)

        slider_row = QtWidgets.QHBoxLayout()
        slider_row.setSpacing(8)
        self._angle_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._angle_slider.setRange(-180, 180)
        self._angle_slider.setValue(int(round(current_angle if current_angle is not None else -90.0)))
        self._angle_label = QtWidgets.QLabel(
            "{}\u00b0".format(self._angle_slider.value()))
        self._angle_label.setFixedWidth(36)
        _theme.set_qss(self._angle_label, "color:#dfe3ff; font-size:10px;")
        slider_row.addWidget(self._angle_slider, 1)
        slider_row.addWidget(self._angle_label)
        row.addLayout(slider_row)

        has_override = current_angle is not None
        self._angle_check.setChecked(has_override)
        slider_row_widget_enabled = has_override
        self._angle_slider.setEnabled(slider_row_widget_enabled)

        def _on_check(checked):
            self._angle_slider.setEnabled(checked)
            self._set_angle(float(self._angle_slider.value()) if checked else None)

        def _on_slide(value):
            self._angle_label.setText("{}\u00b0".format(value))
            if self._angle_check.isChecked():
                self._set_angle(float(value))

        self._angle_check.toggled.connect(_on_check)
        self._angle_slider.valueChanged.connect(_on_slide)
        return row

    def _build_slot_tab(self, i, data):
        page = QtWidgets.QWidget()
        pl = QtWidgets.QVBoxLayout(page)
        pl.setContentsMargins(8, 8, 8, 8)
        pl.setSpacing(6)

        pos_lbl = QtWidgets.QLabel(
            "Slot {} — {}".format(i + 1, _SLOT_POSITIONS[i]))
        _theme.set_qss(pos_lbl, "color:#7fa8d8; font-size:10px; font-weight:bold;")
        pl.addWidget(pos_lbl)

        row = QtWidgets.QHBoxLayout()
        name_e = QtWidgets.QLineEdit(data.get("name", ""))
        name_e.setPlaceholderText("Name")
        _theme.set_qss(name_e, _SS_INPUT)
        tip_e = QtWidgets.QLineEdit(data.get("tooltip", ""))
        tip_e.setPlaceholderText("Tooltip")
        _theme.set_qss(tip_e, _SS_INPUT)
        type_b = QtWidgets.QComboBox()
        type_b.addItems(["MEL", "Python"])
        type_b.setCurrentIndex(1 if (data.get("type", "mel") or "mel").lower() == "python" else 0)
        _theme.set_qss(type_b, _SS_INPUT)
        row.addWidget(QtWidgets.QLabel("Name"))
        row.addWidget(name_e, 1)
        row.addWidget(QtWidgets.QLabel("Tip"))
        row.addWidget(tip_e, 1)
        row.addWidget(type_b)
        pl.addLayout(row)

        code_e = QtWidgets.QTextEdit(data.get("code", ""))
        code_e.setMinimumHeight(90)
        _theme.set_qss(code_e, _SS_INPUT)
        pl.addWidget(code_e)

        icon_row = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel()
        icon_lbl.setFixedSize(22, 22)
        _theme.set_qss(icon_lbl, "background:#0e1018; border:1px solid #2c3348; border-radius:3px;")
        icon_lbl.setToolTip(
            "Right-click to choose this pie icon from a shelf or local file")
        icon_lbl.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        icon_lbl.customContextMenuRequested.connect(
            lambda pos, idx=i, il=icon_lbl: self._show_icon_context_menu(idx, il, pos))
        self._apply_icon_preview(icon_lbl, data.get("icon", ""), i)
        icon_row.addWidget(icon_lbl)

        pick_btn = QtWidgets.QPushButton("↓ Pick from Shelf")
        _theme.set_qss(pick_btn, _SS_BTN)
        pick_btn.clicked.connect(
            lambda _=False, idx=i, ce=code_e, tb=type_b, ne=name_e,
                   te=tip_e, il=icon_lbl: self._pick_from_shelf(idx, ce, tb, ne, te, il))
        icon_row.addWidget(pick_btn)

        clear_icon_btn = QtWidgets.QPushButton("Clear Icon")
        _theme.set_qss(clear_icon_btn, _SS_BTN)
        clear_icon_btn.clicked.connect(
            lambda _=False, idx=i, il=icon_lbl: self._clear_icon(idx, il))
        icon_row.addWidget(clear_icon_btn)
        icon_row.addStretch(1)
        pl.addLayout(icon_row)

        btn_row = QtWidgets.QHBoxLayout()
        test_btn = QtWidgets.QPushButton("Test")
        _theme.set_qss(test_btn, _SS_BTN)
        test_btn.clicked.connect(lambda _=False, ce=code_e, tb=type_b: self._test(ce, tb))
        btn_row.addWidget(test_btn)

        clear_slot_btn = QtWidgets.QPushButton("Clear Slot")
        _theme.set_qss(clear_slot_btn, _SS_BTN)
        clear_slot_btn.clicked.connect(
            lambda _=False, idx=i: self._clear_slot(idx))
        btn_row.addWidget(clear_slot_btn)

        copy_btn = QtWidgets.QPushButton("Copy")
        _theme.set_qss(copy_btn, _SS_BTN)
        copy_btn.clicked.connect(lambda _=False, idx=i: self._copy_slot(idx))
        btn_row.addWidget(copy_btn)

        paste_btn = QtWidgets.QPushButton("Paste")
        _theme.set_qss(paste_btn, _SS_BTN)
        paste_btn.clicked.connect(lambda _=False, idx=i: self._paste_slot(idx))
        btn_row.addWidget(paste_btn)

        btn_row.addStretch(1)

        up_btn = QtWidgets.QPushButton("▲ Move Up")
        _theme.set_qss(up_btn, _SS_BTN)
        up_btn.clicked.connect(lambda _=False, idx=i: self._move_slot(idx, -1))
        btn_row.addWidget(up_btn)

        down_btn = QtWidgets.QPushButton("▼ Move Down")
        _theme.set_qss(down_btn, _SS_BTN)
        down_btn.clicked.connect(lambda _=False, idx=i: self._move_slot(idx, 1))
        btn_row.addWidget(down_btn)

        pl.addLayout(btn_row)
        pl.addStretch(1)

        self._name_edits.append(name_e)
        self._tip_edits.append(tip_e)
        self._type_boxes.append(type_b)
        self._code_edits.append(code_e)
        self._icon_lbls.append(icon_lbl)
        return page

    # ------------------------------------------------------------ helpers
    def _apply_icon_preview(self, label_widget, icon_name, slot_index=None):
        candidates = []
        if slot_index is not None and 0 <= slot_index < len(self._icon_candidates):
            candidates = self._icon_candidates[slot_index]
        data = {"icon": icon_name, "icon_candidates": candidates}
        if (icon_name or candidates) and self._icon_resolver:
            try:
                icon = self._icon_resolver(icon_name, data)
            except TypeError:
                try:
                    icon = self._icon_resolver(icon_name)
                except Exception:
                    icon = None
            except Exception:
                icon = None
            if icon is not None:
                try:
                    label_widget.setPixmap(icon.pixmap(18, 18))
                    return
                except Exception:
                    pass
        label_widget.setPixmap(QtGui.QPixmap())

    def _slot_dict(self, i):
        return {
            "name":    self._name_edits[i].text().strip(),
            "tooltip": self._tip_edits[i].text().strip(),
            "type":    "python" if self._type_boxes[i].currentIndex() == 1 else "mel",
            "code":    self._code_edits[i].toPlainText(),
            "icon":    self._icon_names[i],
            "icon_candidates": list(self._icon_candidates[i]),
        }

    def _set_slot_ui(self, i, data):
        self._name_edits[i].setText(data.get("name", ""))
        self._tip_edits[i].setText(data.get("tooltip", ""))
        self._type_boxes[i].setCurrentIndex(
            1 if (data.get("type", "mel") or "mel").lower() == "python" else 0)
        self._code_edits[i].setPlainText(data.get("code", ""))
        self._icon_names[i] = data.get("icon", "")
        raw_candidates = data.get("icon_candidates", [])
        self._icon_candidates[i] = (
            list(raw_candidates) if isinstance(raw_candidates, (list, tuple)) else [])
        self._apply_icon_preview(self._icon_lbls[i], self._icon_names[i], i)

    def _pick_from_shelf(self, i, code_widget, type_combo, name_widget,
                          tooltip_widget, icon_label):
        try:
            from .shelf_picker import ShelfPickerDialog as _SPD
        except ImportError:
            try:
                from phoenix_panel.shelf_picker import ShelfPickerDialog as _SPD
            except ImportError:
                return
        dlg = _SPD(parent=self)
        accepted = dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        if accepted != QtWidgets.QDialog.Accepted:
            return
        selected = dlg.selected_buttons()
        if not selected:
            return
        btn = selected[0]
        code_widget.setPlainText(btn.get("command", ""))
        src = (btn.get("sourceType", "mel") or "mel").lower()
        idx = type_combo.findText("MEL" if src == "mel" else "Python",
                                    QtCore.Qt.MatchFixedString)
        if idx >= 0:
            type_combo.setCurrentIndex(idx)
        label = (btn.get("label", "") or "").strip() or (btn.get("name", "") or "").strip()
        name_widget.setText(label)
        tooltip_widget.setText((btn.get("annotation", "") or "").strip())
        self._icon_names[i] = btn.get("icon", "")
        self._icon_candidates[i] = list(btn.get("icon_candidates", []) or [])
        self._apply_icon_preview(icon_label, self._icon_names[i], i)

    def _show_icon_context_menu(self, i, icon_label, pos):
        menu = QtWidgets.QMenu(self)
        shelf_action = menu.addAction("Choose from Shelf...")
        local_action = menu.addAction("Choose Local File...")
        menu.addSeparator()
        clear_action = menu.addAction("Clear Icon")
        global_pos = icon_label.mapToGlobal(pos)
        chosen = menu.exec_(global_pos) if hasattr(menu, "exec_") else menu.exec(global_pos)
        if chosen == shelf_action:
            self._pick_icon_only_from_shelf(i, icon_label)
        elif chosen == local_action:
            self._pick_local_icon(i, icon_label)
        elif chosen == clear_action:
            self._clear_icon(i, icon_label)

    def _pick_icon_only_from_shelf(self, i, icon_label):
        try:
            from .shelf_picker import ShelfPickerDialog as _SPD
        except ImportError:
            try:
                from phoenix_panel.shelf_picker import ShelfPickerDialog as _SPD
            except ImportError:
                return
        dlg = _SPD(parent=self)
        dlg.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        accepted = dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        if accepted != QtWidgets.QDialog.Accepted:
            return
        selected = dlg.selected_buttons()
        if not selected:
            return
        self._icon_names[i] = selected[0].get("icon", "") or ""
        self._icon_candidates[i] = list(selected[0].get("icon_candidates", []) or [])
        self._apply_icon_preview(icon_label, self._icon_names[i], i)

    def _pick_local_icon(self, i, icon_label):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose Pie Icon", "",
            "Images (*.png *.svg *.xpm *.bmp *.jpg *.jpeg *.gif);;All Files (*)")
        if not path:
            return
        self._icon_names[i] = path
        self._icon_candidates[i] = []
        self._apply_icon_preview(icon_label, path, i)

    def _clear_icon(self, i, icon_label):
        self._icon_names[i] = ""
        self._icon_candidates[i] = []
        self._apply_icon_preview(icon_label, "", i)

    def _clear_slot(self, i):
        self._icon_names[i] = ""
        self._set_slot_ui(i, _empty_slot())

    def _copy_slot(self, i):
        global _SLOT_CLIPBOARD
        _SLOT_CLIPBOARD = self._slot_dict(i)

    def _paste_slot(self, i):
        if _SLOT_CLIPBOARD is not None:
            self._set_slot_ui(i, dict(_SLOT_CLIPBOARD))

    def _move_slot(self, i, direction):
        j = i + direction
        if not (0 <= j < MAX_PIE_COMMANDS):
            return
        a, b = self._slot_dict(i), self._slot_dict(j)
        self._icon_names[i], self._icon_names[j] = b.get("icon", ""), a.get("icon", "")
        self._set_slot_ui(i, b)
        self._set_slot_ui(j, a)
        self.tabs.setCurrentIndex(j)

    def _test(self, code_widget, type_combo):
        code = code_widget.toPlainText().strip()
        if not code:
            return
        is_python = type_combo.currentIndex() == 1
        try:
            if is_python:
                import __main__
                exec(code, __main__.__dict__)
            else:
                import maya.mel as mel
                mel.eval(code)
        except Exception as e:
            try:
                import maya.cmds as cmds
                cmds.warning("ModPanel pie test: {}".format(e))
            except Exception:
                pass

    def _on_save(self):
        result = []
        for i in range(MAX_PIE_COMMANDS):
            d = self._slot_dict(i)
            if d["code"].strip():
                result.append(d)
        try:
            self._set_pies(result)
        except Exception:
            pass
        self.accept()
