"""The settings panel of the FreeCAD demos: the removal limits (what the rules may remove) as spin boxes, a preset list
and switches per rule. Nothing here decides anything: it edits the settings (src/settings) and tells the demo to apply
them. Runs inside FreeCAD's GUI only.

  step demo (demo_freecad.py)  a tool window; limits can be changed before the removal starts
  Studio (studio_freecad.py)   put into a dock by the caller; Live update, Reset selection, Export STEP, result summary
"""
import html
import os
import sys

from PySide import QtCore, QtWidgets

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
import settings  # noqa: E402

PANEL_NAME = "CleanCADPanel"

# which size limit controls which rule(s); a rule that is not listed here (ref_protrusions, pin_tip, deboss,
# recognizers such as "ml") gets its own on / off box under "Other rules"
FIELD_RULES = {
    "hole_diameter": ("ref_holes",),
    "fillet_radius": ("ref_fillets",),
    "chamfer_size": ("chamfer_edge",),
    "logo_max_depth": ("logo",),
    "boss_max_diameter": ("boss",),
    "rib_max_thickness": ("rib", "rib_simplify"),
}
_MAPPED = {r for rules in FIELD_RULES.values() for r in rules}
OTHER_RULE_TEXT = {"ref_protrusions": "Repeated pressed bumps", "pin_tip": "Pin tips (made plain)",
                   "deboss": "Shallow recesses / debosses"}
LOCKED_NOTE = "Limits can be changed before the removal starts (press ← to come back to the selection)."

STYLE = """
QFrame#section { background: #262a2e; border-radius: 6px; }
QLabel#head { color: #7fb3d5; font-weight: bold; font-size: 11px; }
QPushButton#primary { background: #1f7a8c; color: white; font-weight: bold; padding: 7px; border-radius: 5px; }
QPushButton#primary:disabled { background: #34535a; color: #9aa; }
QLabel#muted { color: #8a9096; }
QLabel#result { background: #1e2a30; border-radius: 6px; padding: 8px; }
"""


class Panel(QtWidgets.QWidget):
    """get_phase() -> demo phase; get_selected() -> number of faces selected now;
    apply_cb(values, rules) -> True if the demo applied them."""

    def __init__(self, parent, rules, preset, get_phase, get_selected, apply_cb, studio=None):
        """studio: None (the step demo: a tool window) or {"reset": fn, "export": fn, "live": bool, "ml": bool}
        (the Studio: the caller puts the panel into a dock)."""
        self.studio = studio
        if studio:
            super().__init__(parent)
        else:
            super().__init__(parent, QtCore.Qt.Tool)
        self.setWindowTitle("CleanCAD – removal settings")
        self.setObjectName(PANEL_NAME)
        self.setMinimumWidth(320)
        self.setStyleSheet(STYLE)
        self.all_rules = list(rules)
        self.get_phase, self.get_selected, self.apply_cb = get_phase, get_selected, apply_cb
        self.spins, self.row_boxes, self.other_boxes = {}, {}, {}

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        self.model_label = QtWidgets.QLabel("-")
        self.model_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.model_label.setWordWrap(True)
        lay.addWidget(self.model_label)

        # ---- preset -------------------------------------------------------------------------------
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Preset"))
        self.preset_box = QtWidgets.QComboBox()
        self.preset_box.setToolTip("Limits for the intended analysis")
        row.addWidget(self.preset_box, 1)
        self.save_btn = QtWidgets.QPushButton("Save…")
        self.save_btn.setToolTip("Save the settings below as a preset")
        self.save_btn.clicked.connect(self._save)
        row.addWidget(self.save_btn)
        lay.addLayout(row)

        # ---- limits -------------------------------------------------------------------------------
        limits, inner = self._section("LIMITS")
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        inner.addLayout(grid)
        for r, f in enumerate(settings.FIELDS):
            use = QtWidgets.QCheckBox(f.label)
            use.setToolTip(f.hint)
            use.toggled.connect(self._changed)
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(f.minimum, f.maximum)
            spin.setSingleStep(f.step)
            spin.setDecimals(2)
            spin.setSuffix(" " + f.unit)
            spin.setToolTip(f.hint)
            spin.valueChanged.connect(self._changed)
            grid.addWidget(use, r, 0)
            grid.addWidget(spin, r, 1)
            self.row_boxes[f.key], self.spins[f.key] = use, spin
        self.keep_box = QtWidgets.QCheckBox("Preserve fastener holes")
        self.keep_box.setToolTip(settings.SWITCHES[0][2])
        self.keep_box.toggled.connect(self._changed)
        grid.addWidget(self.keep_box, len(settings.FIELDS), 0, 1, 2)
        lay.addWidget(limits)

        # ---- other rules --------------------------------------------------------------------------
        others = [r for r in self.all_rules if r not in _MAPPED]
        if others:
            box, col = self._section("OTHER RULES")
            for r in others:
                cb = QtWidgets.QCheckBox(OTHER_RULE_TEXT.get(r, r))
                cb.setToolTip(r)
                cb.setChecked(True)
                cb.toggled.connect(self._changed)
                col.addWidget(cb)
                self.other_boxes[r] = cb
            lay.addWidget(box)

        # ---- recognition (ML) ---------------------------------------------------------------------
        rec, inner_r = self._section("RECOGNITION")
        rrow = QtWidgets.QHBoxLayout()
        inner_r.addLayout(rrow)
        rrow.addWidget(QtWidgets.QLabel(settings.CONFIDENCE[1]))
        self.conf = QtWidgets.QDoubleSpinBox()
        self.conf.setRange(settings.CONFIDENCE[2], settings.CONFIDENCE[3])
        self.conf.setSingleStep(settings.CONFIDENCE[4])
        self.conf.setDecimals(2)
        self.conf.valueChanged.connect(self._changed)
        rrow.addWidget(self.conf)
        self._ml = bool(studio and studio.get("ml"))
        self.conf.setEnabled(self._ml)
        self.conf.setToolTip("Candidates the ML recognizer is less sure of than this are not used. "
                             + ("" if self._ml else "No ML recognizer is connected yet: the rules always report 1.0."))
        lay.addWidget(rec)

        # ---- actions ------------------------------------------------------------------------------
        self.live_box = QtWidgets.QCheckBox("Live update")
        self.live_box.setToolTip("The result follows every change at once. Switch off for big models and press Apply.")
        self.live_box.setChecked(bool(studio and studio.get("live", True)))
        self.live_box.setVisible(bool(studio))
        self.live_box.toggled.connect(self._live_toggled)
        lay.addWidget(self.live_box)
        self.apply_btn = QtWidgets.QPushButton("Apply settings")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self._apply)
        lay.addWidget(self.apply_btn)
        if studio:
            brow = QtWidgets.QHBoxLayout()
            self.reset_btn = QtWidgets.QPushButton("Reset selection")
            self.reset_btn.setToolTip("Forget the faces you added or removed by clicking in the original view")
            self.reset_btn.clicked.connect(studio["reset"])
            brow.addWidget(self.reset_btn)
            self.export_btn = QtWidgets.QPushButton("Export STEP…")
            self.export_btn.clicked.connect(studio["export"])
            brow.addWidget(self.export_btn)
            lay.addLayout(brow)
        self._debounce = QtCore.QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._apply)

        # ---- result -------------------------------------------------------------------------------
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("result")
        self.status.setWordWrap(True)
        self.status.setTextFormat(QtCore.Qt.RichText)
        self.status.setVisible(False)
        lay.addWidget(self.status)
        if studio:
            legend = QtWidgets.QLabel("<span style='color:#d92626'>■</span> selected by the rules<br>"
                                      "<span style='color:#ff8c00'>■</span> added by hand, or could not be removed<br>"
                                      "Click a face in the original to add it or take it out.")
            legend.setObjectName("muted")
            legend.setWordWrap(True)
            lay.addWidget(legend)
        lay.addStretch(1)
        review = QtWidgets.QLabel("Engineer review is required before CAE use.")
        review.setObjectName("muted")
        review.setWordWrap(True)
        lay.addWidget(review)

        self._fill_presets(preset)
        self.preset_box.currentTextChanged.connect(self._preset_chosen)
        self._load(preset)
        self._dirty = False
        self._show_dirty()
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(400)

    # ---- widgets -------------------------------------------------------------------------------------
    @staticmethod
    def _section(title):
        """A framed block with a small heading; returns (the frame to add, the layout to fill)."""
        frame = QtWidgets.QFrame()
        frame.setObjectName("section")
        inner = QtWidgets.QVBoxLayout(frame)
        inner.setContentsMargins(10, 8, 10, 10)
        inner.setSpacing(6)
        head = QtWidgets.QLabel(title)
        head.setObjectName("head")
        inner.addWidget(head)
        return frame, inner

    def _fill_presets(self, select):
        self.preset_box.blockSignals(True)
        self.preset_box.clear()
        self.preset_box.addItems(settings.list_presets())
        self.preset_box.setCurrentText(select)
        self.preset_box.blockSignals(False)

    def set_job(self, name, rules):
        """A new model (or a changed rule list): show its name; rows of rules this job does not use are off."""
        self.model_label.setText(name)
        self.all_rules = list(rules)
        for key in FIELD_RULES:
            if not self._used(key):
                self.row_boxes[key].setChecked(False)

    def set_status(self, text):
        """Result summary; a line that starts with a warning sign is shown in orange."""
        lines = []
        for i, line in enumerate(text.split("\n")):
            safe = html.escape(line)
            if line.startswith("⚠"):
                safe = f"<span style='color:#ffb347'>{safe}</span>"
            elif i == 0 and "→" in line:
                head, _, rest = safe.partition(" · ")
                safe = f"<b>{head}</b>" + (f" · {rest}" if rest else "")
            lines.append(safe)
        self.status.setText("<br>".join(lines))
        self.status.setVisible(bool(text))

    # ---- values --------------------------------------------------------------------------------------
    def values(self):
        v = {k: spin.value() for k, spin in self.spins.items()}
        v["keep_fasteners"] = self.keep_box.isChecked()
        v["min_confidence"] = self.conf.value()
        return settings.normalise(v)

    def active_rules(self):
        out = []
        for r in self.all_rules:
            field = next((k for k, rs in FIELD_RULES.items() if r in rs), None)
            box = self.row_boxes[field] if field else self.other_boxes.get(r)
            if box is None or box.isChecked():
                out.append(r)
        return out

    def _load(self, preset):
        v = settings.load_preset(preset)
        group = list(self.spins.values()) + list(self.row_boxes.values()) + [self.keep_box, self.conf]
        for w in group:
            w.blockSignals(True)
        for k, spin in self.spins.items():
            spin.setValue(v[k])
        self.keep_box.setChecked(v["keep_fasteners"])
        self.conf.setValue(v["min_confidence"])
        for key in FIELD_RULES:
            self.row_boxes[key].setChecked(self._used(key))
        for w in group:
            w.blockSignals(False)
        self._dirty = True
        self._show_dirty()

    # ---- events --------------------------------------------------------------------------------------
    def _preset_chosen(self, name):
        if name:
            self._load(name)
            if self.studio and self.live_box.isChecked():
                self._debounce.start()

    def _changed(self, *_):
        self._dirty = True
        self._show_dirty()
        if self.studio and self.live_box.isChecked():
            self._debounce.start()          # the result follows after the last change (350 ms)

    def _live_toggled(self, on):
        self._show_dirty()
        if on and self._dirty:
            self._debounce.start()

    def _show_dirty(self):
        self.apply_btn.setText("Apply settings  •" if self._dirty else "Apply settings")
        if self.studio:
            self.apply_btn.setVisible(not self.live_box.isChecked())      # with Live update there is nothing to press

    def _apply(self):
        if self.apply_cb(self.values(), self.active_rules()):
            self._dirty = False
            self._show_dirty()
            if not self.studio:
                self.set_status(f"Applied. {self.get_selected()} faces selected.")
        if self.studio:
            return
        try:                                  # give the keys (arrows = next / back) back to the 3D view
            import FreeCADGui as Gui
            Gui.getMainWindow().setFocus()
        except Exception:                     # noqa: BLE001
            pass

    def _save(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Save preset", "Preset name:")
        if not ok or not name.strip():
            return
        try:
            settings.save_preset(name.strip(), self.values())
        except (ValueError, OSError) as e:
            QtWidgets.QMessageBox.warning(self, "Save preset", str(e))
            return
        self._fill_presets(name.strip())
        self.set_status(f"Saved preset '{name.strip()}'\n{settings.presets_dir()}")

    def _used(self, key):
        return any(r in self.all_rules for r in FIELD_RULES[key])

    def _poll(self):
        """Step demo: limits can be changed while it waits at the original model or at the selection, not during the
        removal. Studio: always."""
        phase = self.get_phase()
        editable = True if self.studio else phase in ("orig", "select")
        for key in FIELD_RULES:
            self.row_boxes[key].setEnabled(editable and self._used(key))
            self.spins[key].setEnabled(editable and self._used(key)
                                       and not (key == "hole_diameter" and self.keep_box.isChecked()))
        for r, box in self.other_boxes.items():
            box.setEnabled(editable and r in self.all_rules)
        for w in (self.keep_box, self.preset_box, self.apply_btn):
            w.setEnabled(editable)
        self.conf.setEnabled(editable and self._ml)
        if phase and not editable:
            self.set_status(LOCKED_NOTE)
        elif editable and not self.studio and LOCKED_NOTE[:20] in self.status.text():
            self.set_status("")


def contains(widget):
    """True if `widget` is part of the panel (the demo's key handler must leave typing in the panel alone)."""
    while widget is not None:
        if widget.objectName() == PANEL_NAME:
            return True
        widget = widget.parentWidget()
    return False
