"""CleanCAD Studio inside FreeCAD: ORIGINAL (left) and PROCESSED (right) side by side, the removal settings in a dock on
the left, the result following every change at once, and the two views moving together like one.

Run inside FreeCAD's GUI (see fcdemo.sh / hp_demo.sh), not with FreeCADCmd. One STEP file: CLEANCAD_INPUT, the rules
CLEANCAD_RULE (comma-separated), the starting preset CLEANCAD_PROFILE.

  - the original view shows what the rules selected in red; click a face to add it (orange) or, if it is red, to take
    it out of the selection: the processed view is made again at once
  - changing a limit / a rule switch in the dock does the same (Live update; for big models switch it off and press Apply)
  - rotating, panning or zooming either view moves the other one the same way

All results (exported STEP, logs, snapshots) are written under $CLEANCAD_WORKDIR - nothing in the repo.
"""
import os
import re
import sys
import time

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtGui, QtWidgets

WORKDIR = os.environ.get("CLEANCAD_WORKDIR", os.path.expanduser("~/Documents/CleanCAD_Workspace"))
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine"), os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402
import live  # noqa: E402
import settings  # noqa: E402
import panel as settings_panel  # noqa: E402

GRAY, RED, ORANGE = (0.75, 0.78, 0.82), (0.85, 0.12, 0.12), (1.0, 0.55, 0.0)
DOCK_NAME = "CleanCADDock"
LIVE_MAX_FACES = 150           # bigger models start with Live update off (every change would take long)
UPDATE_BUDGET = 120.0          # seconds for one update; what is not removed by then is reported
VOLUME_WARN = 5.0              # percent
S = {}                         # the state of the session

view_prefs = App.ParamGet("User parameter:BaseApp/Preferences/View")
view_prefs.SetBool("UseNavigationAnimations", False)
view_prefs.SetBool("UseAutoRotation", False)
os.makedirs(os.path.join(WORKDIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(WORKDIR, "snapshots"), exist_ok=True)
os.makedirs(os.path.join(WORKDIR, "samples", "examples", "out"), exist_ok=True)


def log(message):
    with open(os.path.join(WORKDIR, "logs", f"{S.get('name', 'studio')}_studio.log"), "a") as f:
        f.write(time.strftime("%H:%M:%S ") + message + "\n")


def snapshot(tag):
    Gui.updateGui()
    path = os.path.join(WORKDIR, "snapshots", f"{S['name']}_studio_{tag}.png")
    QtGui.QGuiApplication.primaryScreen().grabWindow(Gui.getMainWindow().winId()).save(path)
    return path


# ---------------------------------------------------------------------------------------------------- window
_hidden = []


class _RestoreOnClose(QtCore.QObject):
    """Brings the panels and toolbars back when the window closes, so FreeCAD's normal layout (saved on exit) is kept."""

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Close:
            for widget in _hidden:
                widget.show()
        return False


def declutter():
    """Hide FreeCAD's own panels and toolbars (not ours): the two views get the room."""
    main = Gui.getMainWindow()
    if not _hidden:
        try:
            Gui.activateWorkbench("PartWorkbench")      # Part Design would ask to create a body (a task panel)
        except Exception:                               # noqa: BLE001
            pass
    try:
        Gui.Control.closeDialog()
    except Exception:                                   # noqa: BLE001
        pass
    overlays = [w for w in main.findChildren(QtWidgets.QWidget)
                if "Overlay" in w.metaObject().className() or "TaskView" in w.metaObject().className()]
    for widget in (main.findChildren(QtWidgets.QDockWidget) + main.findChildren(QtWidgets.QToolBar) + overlays):
        if widget.objectName() == DOCK_NAME:
            continue                                    # our own dock stays
        if widget.isVisible():
            if widget not in _hidden:
                _hidden.append(widget)
            widget.hide()
    if not getattr(main, "_cleancad_filter", None):
        main._cleancad_filter = _RestoreOnClose(main)
        main.installEventFilter(main._cleancad_filter)
    Gui.updateGui()


class _Resize(QtCore.QObject):
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Resize:
            QtCore.QTimer.singleShot(0, arrange)
        return False


def arrange():
    """ORIGINAL on the left half, PROCESSED on the right half of the area in the middle."""
    main = Gui.getMainWindow()
    mdi = main.findChild(QtWidgets.QMdiArea)
    if mdi is None:
        return
    mdi.setViewMode(QtWidgets.QMdiArea.SubWindowView)
    left, right = S.get("sub_l"), S.get("sub_r")
    if left is None or right is None:
        for sub in mdi.subWindowList():
            title = sub.windowTitle()
            if S["dl"].Label in title:
                left = sub
            elif S["dr"].Label in title:
                right = sub
        if left is None or right is None:
            return
        for sub, text in ((left, "ORIGINAL   ·   red = selected for removal"), (right, "PROCESSED   ·   result")):
            # no minimise / maximise / close buttons: the two panes are fixed, only their title is kept
            sub.setWindowFlags(QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowTitleHint)
            sub.setWindowTitle(text)
        S["sub_l"], S["sub_r"] = left, right
    for sub in mdi.subWindowList():
        if sub is not left and sub is not right:
            sub.hide()                                  # e.g. FreeCAD's Start page
    w, h = mdi.viewport().width(), mdi.viewport().height()
    for sub, x, width in ((left, 0, w // 2), (right, w // 2, w - w // 2)):
        sub.showNormal()
        sub.setGeometry(x, 0, width, h)
    if not S.get("resize_filter"):
        S["resize_filter"] = _Resize(mdi)
        mdi.viewport().installEventFilter(S["resize_filter"])


def view(doc):
    gd = Gui.getDocument(doc.Name)
    return gd.activeView() if gd else None


# ---------------------------------------------------------------------------------------------------- camera
def sync_cameras():
    """Whichever view the user moved, the other one follows (the camera text of both is compared 30 times a second)."""
    vl, vr = S.get("vl"), S.get("vr")
    if vl is None or vr is None:
        return
    try:
        a, b = vl.getCamera(), vr.getCamera()
    except Exception:                                   # noqa: BLE001
        return
    if a != S["cam_l"]:
        vr.setCamera(a)
        S["cam_l"], S["cam_r"] = a, vr.getCamera()
    elif b != S["cam_r"]:
        vl.setCamera(b)
        S["cam_r"], S["cam_l"] = b, vl.getCamera()


def fit_both():
    S["vl"].viewIsometric()
    try:
        S["vl"].fitAll(1.15)
    except Exception:                                   # noqa: BLE001
        S["vl"].fitAll()
    S["vr"].setCamera(S["vl"].getCamera())
    S["cam_l"], S["cam_r"] = S["vl"].getCamera(), S["vr"].getCamera()


# ---------------------------------------------------------------------------------------------------- the result
def selection():
    return (S["auto"] - S["manual_remove"]) | S["manual_add"]


def recognise():
    """What the active rules select in the ORIGINAL (with the limits now in core.PROFILE)."""
    t0 = time.monotonic()
    S["auto"] = {core.sig(f) for f in core.select(S["source"], S["active_rules"])}
    log(f"AUTO-SELECTION {len(S['auto'])} faces with rules {S['active_rules']} in {time.monotonic() - t0:.2f} s")


def paint():
    src = S["source"]
    sel = selection()
    S["ol"].ViewObject.DiffuseColor = [(RED if core.sig(f) in S["auto"] else ORANGE) if core.sig(f) in sel else GRAY
                                       for f in src.Faces]
    res = S["result"]
    S["or"].ViewObject.DiffuseColor = [ORANGE if core.sig(f) in res.failed else GRAY for f in res.shape.Faces]


def update():
    """Make the PROCESSED model from the ORIGINAL and the selection now (the original is never changed)."""
    if S.get("busy"):
        S["again"] = True
        return
    S["busy"] = True
    try:
        S["panel"].set_status("Processing…")
        Gui.updateGui()
        res = live.remove_selected(S["source"], selection(), budget=UPDATE_BUDGET)
        S["result"] = res
        S["or"].Shape = res.shape
        S["dr"].recompute()
        paint()
        src, shape = S["source"], res.shape
        vol = ""
        if src.Solids and shape.Solids and src.Volume:
            change = (shape.Volume - src.Volume) / src.Volume * 100
            vol = f" · volume {change:+.1f} %" + ("  ⚠ check" if abs(change) >= VOLUME_WARN else "")
        text = (f"{len(src.Faces)} → {len(shape.Faces)} faces · {len(selection())} selected · "
                f"{res.removed} feature(s) removed{vol} · {res.seconds:.1f} s")
        if res.failures:
            text += f"\n⚠ {len(res.failures)} feature(s) could not be removed (orange on the right): kept as they are"
        if res.stopped:
            text += "\n⚠ time budget used up: the rest was not processed"
        S["panel"].set_status(text)
        log("UPDATE " + text.replace("\n", " | "))
    except Exception:                                   # noqa: BLE001
        import traceback
        log("ERROR in update:\n" + traceback.format_exc())
        S["panel"].set_status("Internal error - see logs/" + S["name"] + "_studio.log")
    finally:
        S["busy"] = False
        Gui.updateGui()
    if S.pop("again", False):
        QtCore.QTimer.singleShot(0, update)


def apply_settings(values, rules):
    """Called by the dock: new limits / rule switches -> select again, make the result again."""
    core.apply_settings(values)
    S["active_rules"] = list(rules)
    log(f"SETTINGS {core.PROFILE} rules={rules}")
    recognise()
    update()
    return True


def toggle_face(index):
    """index: 1-based face number in the ORIGINAL view (the 'FaceN' of a click)."""
    faces = S["source"].Faces
    if not 1 <= index <= len(faces):
        return
    s = core.sig(faces[index - 1])
    if s in selection():
        S["manual_add"].discard(s)
        if s in S["auto"]:
            S["manual_remove"].add(s)
        log(f"CLICK face {index}: taken out of the selection")
    else:
        S["manual_remove"].discard(s)
        if s not in S["auto"]:
            S["manual_add"].add(s)
        log(f"CLICK face {index}: added to the selection")
    update()


def reset_manual():
    S["manual_add"].clear()
    S["manual_remove"].clear()
    log("hand-made selection reset")
    update()


def export_step():
    default = os.path.join(WORKDIR, "samples", "examples", "out", f"{S['name']}_defeatured.step")
    path, _ = QtWidgets.QFileDialog.getSaveFileName(Gui.getMainWindow(), "Export STEP", default, "STEP (*.step *.stp)")
    if not path:
        return
    S["result"].shape.exportStep(path)
    back = Part.read(path)
    ok = back.isValid() and len(back.Faces) == len(S["result"].shape.Faces)
    S["panel"].set_status(f"Exported {path}\nRe-import check: {'OK' if ok else 'FAILED'}")
    log(f"EXPORT {path} reimport_ok={ok}")


class _Picker:
    """A click on a face of the ORIGINAL view adds / removes it."""

    def addSelection(self, doc, obj, sub, pnt):
        if doc != S["dl"].Name or obj != S["ol"].Name or not sub.startswith("Face"):
            return
        try:
            toggle_face(int(sub[4:]))
        finally:
            Gui.Selection.clearSelection()


# ---------------------------------------------------------------------------------------------------- start
def start():
    file = os.environ["CLEANCAD_INPUT"]
    rules = [r for r in os.environ.get("CLEANCAD_RULE", ",".join(core.all_rules())).split(",") if r in core.RULES]
    preset = os.environ.get("CLEANCAD_PROFILE", settings.DEFAULT_PRESET)
    source = Part.read(file)
    S.update(name=os.path.splitext(os.path.basename(file))[0], source=source, rules=rules, active_rules=list(rules),
             auto=set(), manual_add=set(), manual_remove=set(), busy=False)
    open(os.path.join(WORKDIR, "logs", f"{S['name']}_studio.log"), "w").close()
    log(f"START {file} faces={len(source.Faces)} rules={rules} preset={preset}")
    core.apply_settings(settings.load_preset(preset))
    core.GUARD_IN_GUI = len(source.Faces) > LIVE_MAX_FACES    # big models: a stuck kernel call must not freeze the window

    S["dl"] = App.newDocument("Original")
    S["ol"] = S["dl"].addObject("Part::Feature", "Original")
    S["ol"].Shape = source
    S["dr"] = App.newDocument("Processed")
    S["or"] = S["dr"].addObject("Part::Feature", "Processed")
    S["or"].Shape = source.copy()
    S["dl"].recompute()
    S["dr"].recompute()
    QtCore.QTimer.singleShot(400, stage2)


def stage2():
    main = Gui.getMainWindow()
    S["vl"], S["vr"] = view(S["dl"]), view(S["dr"])
    if S["vl"] is None or S["vr"] is None:
        return QtCore.QTimer.singleShot(300, stage2)
    for obj in (S["ol"], S["or"]):
        obj.ViewObject.DisplayMode = "Flat Lines"

    live_on = len(S["source"].Faces) <= LIVE_MAX_FACES
    try:
        import recognition
        ml = "ml" in recognition.available()
    except Exception:                                   # noqa: BLE001
        ml = False
    studio = {"reset": reset_manual, "export": export_step, "live": live_on, "ml": ml}
    S["panel"] = settings_panel.Panel(None, S["rules"], os.environ.get("CLEANCAD_PROFILE", settings.DEFAULT_PRESET),
                                      lambda: "select", lambda: len(selection()), apply_settings, studio=studio)
    S["panel"].set_job(S["name"], S["rules"])
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(S["panel"])
    dock = QtWidgets.QDockWidget("CleanCAD Studio", main)
    dock.setObjectName(DOCK_NAME)
    dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)       # fixed: no float / close buttons
    dock.setWidget(scroll)
    dock.setFixedWidth(350)
    main.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
    S["dock"] = dock

    declutter()
    arrange()
    recognise()
    update()
    fit_both()
    for delay in (600, 1500, 3500):                     # FreeCAD may open a panel / the Start page a little late
        QtCore.QTimer.singleShot(delay, lambda: (declutter(), arrange(), fit_both()))
    if not live_on:
        S["panel"].set_status(S["panel"].status.text() + "\nBig model: Live update is off, press Apply after a change.")

    S["timer"] = QtCore.QTimer()
    S["timer"].timeout.connect(sync_cameras)
    S["timer"].start(33)
    S["picker"] = _Picker()
    Gui.Selection.addObserver(S["picker"])
    if os.environ.get("CLEANCAD_STUDIO_TEST") == "1":
        QtCore.QTimer.singleShot(5000, test_sequence)


def test_sequence():
    """Unattended check (CLEANCAD_STUDIO_TEST=1): pictures and counts go to snapshots/ and the log."""
    p = S["panel"]
    snapshot("00_start")
    log(f"TEST start: selected {len(selection())} faces, result faces {len(S['result'].shape.Faces)}")
    p.spins["fillet_radius"].setValue(0.1)
    p._apply()
    log(f"TEST fillet_radius 0.1: selected {len(selection())}, result faces {len(S['result'].shape.Faces)}")
    snapshot("01_small_limit")
    p.spins["fillet_radius"].setValue(10.0)
    p._apply()
    log(f"TEST fillet_radius 10: selected {len(selection())}, result faces {len(S['result'].shape.Faces)}")
    toggle_face(1)
    log(f"TEST face 1 clicked: selected {len(selection())}, result faces {len(S['result'].shape.Faces)}")
    snapshot("02_clicked_face")
    # the second view follows the first
    S["vl"].viewTop()

    def check_sync():
        pick = lambda text: re.search(r"orientation\s+(\S+\s+\S+\s+\S+\s+\S+)", text).group(1)   # noqa: E731
        log(f"TEST left view turned to top: left {pick(S['vl'].getCamera())} | right {pick(S['vr'].getCamera())}")

    QtCore.QTimer.singleShot(500, check_sync)
    QtCore.QTimer.singleShot(900, lambda: snapshot("03_synced_top"))


start()
