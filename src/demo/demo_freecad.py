"""Live FreeCAD GUI demo of the CleanCAD prototype: highlights faces selected for removal in
red, then removes them feature-by-feature with the 3D view updating in real time.

Run inside FreeCAD's GUI (see fcdemo.sh), not with FreeCADCmd.

Jobs come from $CLEANCAD_WORKDIR/samples/examples/manifest.json (all examples, or a subset
via CLEANCAD_ONLY=name1,name2), or a single external file via CLEANCAD_INPUT + CLEANCAD_RULE.
All results (STEP, snapshots, logs) are written under $CLEANCAD_WORKDIR - nothing in the repo.
"""
import math
import os
import re
import sys
import json
import time

import FreeCAD as App
import FreeCADGui as Gui
import Part
import ImportGui
from PySide import QtCore, QtGui, QtWidgets

WORKDIR = os.environ.get("CLEANCAD_WORKDIR", os.path.expanduser("~/Documents/CleanCAD_Workspace"))
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):                       # layers: engine/, rules/, ...
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core

DELAY_MS = int(os.environ.get("CLEANCAD_DELAY_MS", "1200"))
FAIL_HOLD_MS = int(os.environ.get("CLEANCAD_FAIL_HOLD_MS", "4500"))
AUTOQUIT = os.environ.get("CLEANCAD_AUTOQUIT") == "1"
# Interactive by default: the arrow keys step through the demo and faces can be clicked to add them to /
# remove them from the selection. CLEANCAD_AUTO=1 keeps the old timer-driven run (used for unattended runs).
INTERACTIVE = os.environ.get("CLEANCAD_AUTO") != "1"
BANNER_STEP = "#1f4e79"
UI_ALPHA = 0.78            # opacity of the on-screen messages (1.0 = solid)
GRAY, RED, ORANGE = (0.75, 0.78, 0.82), (0.85, 0.12, 0.12), (1.0, 0.55, 0.0)
BANNER_FAIL, BANNER_OK = "#c0392b", "#2e7d32"

# Instant camera moves so screenshots aren't caught mid-animation.
view_prefs = App.ParamGet("User parameter:BaseApp/Preferences/View")
view_prefs.SetBool("UseNavigationAnimations", False)
view_prefs.SetBool("UseAutoRotation", False)

os.makedirs(os.path.join(WORKDIR, "samples", "examples", "highlight"), exist_ok=True)
os.makedirs(os.path.join(WORKDIR, "samples", "examples", "out"), exist_ok=True)
FAIL_DIR = os.path.join(WORKDIR, "samples", "examples", "failures")
os.makedirs(FAIL_DIR, exist_ok=True)
os.makedirs(os.path.join(WORKDIR, "snapshots"), exist_ok=True)
os.makedirs(os.path.join(WORKDIR, "logs"), exist_ok=True)

if os.environ.get("CLEANCAD_INPUT"):
    single = os.environ["CLEANCAD_INPUT"]
    jobs = [dict(name=os.path.splitext(os.path.basename(single))[0], file=single,
                 rules=os.environ.get("CLEANCAD_RULE", "cyl").split(","))]
else:
    manifest_path = os.path.join(WORKDIR, "samples", "examples", "manifest.json")
    jobs = json.load(open(manifest_path))
    if os.environ.get("CLEANCAD_ONLY"):
        wanted = set(os.environ["CLEANCAD_ONLY"].split(","))
        jobs = [j for j in jobs if j["name"] in wanted]

state = {}


def log(message):
    with open(os.path.join(WORKDIR, "logs", f"{state['job']['name']}.log"), "a") as f:
        f.write(time.strftime("%H:%M:%S ") + message + "\n")


def paint():
    ctx = core.Ctx(state["obj"].Shape)
    fns = [core.RULES[r] for r in state["job"]["rules"]]

    def color(f):
        if core.sig(f) in state["failed"]:
            return ORANGE  # selected for removal but the removal failed
        return RED if any(fn(f, ctx) for fn in fns) else GRAY

    state["vo"].DiffuseColor = [color(f) for f in state["obj"].Shape.Faces]


def paint_before():
    """The static BEFORE copy (shown to the left): original shape, faces selected for removal in red."""
    src = state["source"]
    if INTERACTIVE:
        chosen = state["sel"]
        state["before"].ViewObject.DiffuseColor = [RED if core.sig(f) in chosen else GRAY for f in src.Faces]
        return
    ctx = core.Ctx(src)
    fns = [core.RULES[r] for r in state["job"]["rules"]]
    state["before"].ViewObject.DiffuseColor = [
        RED if any(fn(f, ctx) for fn in fns) else GRAY for f in src.Faces]


_banner = {}
_legend = {}

_dismissed = set()          # message kinds the user closed with the X (all come back with the H key)


class MessageLabel(QtWidgets.QLabel):
    """An on-screen message with an X in its top right corner; the X follows the label's size. Closing it
    keeps that kind of message hidden until the H key brings the messages back."""

    def __init__(self, parent, kind):
        super().__init__(parent)
        self.kind = kind
        self.button = QtWidgets.QPushButton("\u2715", self)
        self.button.setFlat(True)
        self.button.setCursor(QtCore.Qt.PointingHandCursor)
        self.button.setStyleSheet("background:transparent; color:white; font-size:18px; font-weight:bold; "
                                  "border:none; padding:0; min-width:0; min-height:0;")
        self.button.setFixedSize(28, 28)
        self.button.clicked.connect(self._dismiss)

    def _dismiss(self):
        _dismissed.add(self.kind)
        self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.button.move(max(0, self.width() - self.button.width() - 4), 2)
        self.button.raise_()


def _close_button(label, kind):
    label.button.move(max(0, label.width() - label.button.width() - 4), 2)
    label.button.raise_()


def _shown(kind):
    return kind not in _dismissed


def toggle_messages():
    """H key: bring closed messages back, or close them all."""
    if _dismissed:
        _dismissed.clear()
        for refresh in (_refresh_banner, _refresh_legend, _refresh_counter, lambda: show_swatch(state.get("phase") in ("select", "removing"))):
            refresh()
    else:
        _dismissed.update(("banner", "legend", "counter", "swatch"))
        for lab in (_banner, _legend, _counter, _swatch):
            if "label" in lab:
                lab["label"].hide()



def show_legend(text):
    main = Gui.getMainWindow()
    if "label" not in _legend:
        label = MessageLabel(main, "legend")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("background:rgba(0,0,0,170); color:white; font-size:16px; padding:6px;")
        _legend["label"] = label
    label = _legend["label"]
    label.setText(text)
    _legend["text"] = text
    _set_opacity(label, UI_ALPHA)
    area = main.centralWidget()
    origin = area.mapTo(main, QtCore.QPoint(0, 0))
    label.setGeometry(origin.x() + 20, origin.y() + area.height() - 84, area.width() - 40, 34)
    _close_button(label, "legend")
    if _shown("legend"):
        label.show()
        label.raise_()


def _refresh_legend():
    if "text" in _legend:
        show_legend(_legend["text"])


def hide_legend():
    if "label" in _legend:
        _legend["label"].hide()


def show_banner(text, bg, height=100):
    """On-screen message over the 3D view, so a failure can't be mistaken for a crash."""
    main = Gui.getMainWindow()
    if "label" not in _banner:
        label = MessageLabel(main, "banner")
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignCenter)
        _banner["label"] = label
    label = _banner["label"]
    label.setStyleSheet(f"background:{bg}; color:white; font-size:20px; font-weight:bold; padding:10px;")
    label.setText(text)
    _banner["args"] = (text, bg, height)
    _set_opacity(label, UI_ALPHA)
    area = main.centralWidget()
    origin = area.mapTo(main, QtCore.QPoint(0, 0))
    label.setGeometry(origin.x() + 20, origin.y() + 12, area.width() - 40, height)
    _close_button(label, "banner")
    if _shown("banner"):
        label.show()
        label.raise_()
    Gui.updateGui()


def _refresh_banner():
    if "args" in _banner:
        show_banner(*_banner["args"])


def hide_banner():
    if "label" in _banner:
        _banner["label"].hide()


def ensure_active():
    """Keep our document's 3D view in front (FreeCAD can open its Start page late and steal focus).
    Returns True if it had to switch back."""
    doc = state.get("doc")
    mdi = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    if doc is None or mdi is None:
        return False
    current = mdi.activeSubWindow()
    if current is not None and doc.Name in current.windowTitle():
        return False
    for sub in mdi.subWindowList():
        if doc.Name in sub.windowTitle():
            Gui.setActiveDocument(doc.Name)
            mdi.setActiveSubWindow(sub)
            Gui.updateGui()
            return True
    return False


_hidden = []


class _RestoreOnClose(QtCore.QObject):
    """Brings the side panels and toolbars back when the window closes, so the user's normal FreeCAD
    layout (which FreeCAD saves on exit) is not changed by the demo."""

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Close:
            for widget in _hidden:
                widget.show()
        return False


def declutter():
    """Hide the model tree and task panels (not the toolbars) so the 3D view is wider. Called again on every
    refocus: FreeCAD may open a task panel a few seconds after launch."""
    main = Gui.getMainWindow()
    if not _hidden:
        try:
            Gui.activateWorkbench("PartWorkbench")   # Part Design would ask to create a body (a task panel)
        except Exception:                            # noqa: BLE001
            pass
    try:
        Gui.Control.closeDialog()
    except Exception:                                # noqa: BLE001
        pass
    overlays = [w for w in main.findChildren(QtWidgets.QWidget)
                if "Overlay" in w.metaObject().className() or "TaskView" in w.metaObject().className()]
    for widget in main.findChildren(QtWidgets.QDockWidget) + overlays:
        if widget.isVisible():
            if widget not in _hidden:
                _hidden.append(widget)
            widget.hide()
    if not getattr(main, "_cleancad_filter", None):
        main._cleancad_filter = _RestoreOnClose(main)       # keep a reference
        main.installEventFilter(main._cleancad_filter)
    Gui.updateGui()


def fit_view(iso=False):
    view = Gui.activeDocument().activeView()
    if iso:
        view.viewIsometric()
    try:
        view.fitAll(1.25)     # zoom out a little: room for the banner on top and the counter at the bottom
    except Exception:         # noqa: BLE001
        view.fitAll()
    Gui.updateGui()


def face_view_fn(face):
    """A function that sets the standard view looking at the side the face points to (e.g. a bottom face)."""
    n = core.normal(face)
    if n is None:
        return None
    axis = max("xyz", key=lambda a: abs(getattr(n, a)))
    positive = getattr(n, axis) > 0
    names = {("x", True): "viewRight", ("x", False): "viewLeft", ("y", True): "viewRear",
             ("y", False): "viewFront", ("z", True): "viewTop", ("z", False): "viewBottom"}
    return lambda view: getattr(view, names[(axis, positive)])()


def _read_cam(view):
    """Camera as (inventor text, position, ortho height or None). Parsed from the text because pivy isn't available."""
    text = view.getCamera()
    pos = App.Vector(*[float(v) for v in re.search(r"position\s+(\S+)\s+(\S+)\s+(\S+)", text).groups()])
    m = re.search(r"\bheight\s+(\S+)", text)
    return text, pos, (float(m.group(1)) if m else None)


def _write_cam(view, text, pos, height, rot=None):
    text = re.sub(r"position\s+\S+\s+\S+\s+\S+", f"position {pos.x} {pos.y} {pos.z}", text, count=1)
    if rot is not None:
        ax = rot.Axis
        text = re.sub(r"orientation\s+\S+\s+\S+\s+\S+\s+\S+",
                      f"orientation {ax.x} {ax.y} {ax.z} {rot.Angle}", text, count=1)
    if height is not None:
        text = re.sub(r"\bheight\s+\S+", f"height {height}", text, count=1)
    view.setCamera(text)


def _set_opacity(label, alpha):
    effect = label.graphicsEffect()
    if effect is None:
        effect = QtWidgets.QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)
    effect.setOpacity(alpha)


def animate_view(set_target, on_done, ms=900, on_frame=None, centers=None):
    """Smoothly rotate the camera to the view set by set_target (like orbiting with the middle mouse button).

    centers=(start_center, end_center) additionally glides the framing (pan + zoom) instead of re-fitting
    every frame; on_frame(t) lets the caller fade other things in alongside (t goes 0 -> 1, eased)."""
    view = Gui.activeDocument().activeView()
    glide = False
    try:
        start_rot = view.getCameraOrientation()
        _, start_pos, start_h = _read_cam(view)
        set_target(view)
        if centers:
            view.fitAll()  # frame what the final view shows, then go back and glide there
        end_rot = view.getCameraOrientation()
        end_txt, end_pos, end_h = _read_cam(view)
        _write_cam(view, end_txt, start_pos, start_h)
        view.setCameraOrientation(start_rot)
        glide = centers is not None
    except Exception as e:
        log(f"camera animation unavailable ({e!r}); switching instantly")
        set_target(view)
        view.fitAll()
        if on_frame:
            on_frame(1.0)
        return on_done()
    frames, count = max(1, ms // 33), [0]

    def tick():
        count[0] += 1
        t = count[0] / frames
        s = t * t * (3 - 2 * t)  # ease in/out
        rot = start_rot.slerp(end_rot, s)
        view.setCameraOrientation(rot)
        if glide:
            c0, c1 = centers
            center = c0 + (c1 - c0) * s
            dist = (start_pos - c0).Length * (1 - s) + (end_pos - c1).Length * s
            pos = center + rot.multVec(App.Vector(0, 0, dist))
            _write_cam(view, end_txt, pos, None if start_h is None else start_h * (1 - s) + end_h * s)
            view.setCameraOrientation(rot)
        else:
            view.fitAll()
        if on_frame:
            on_frame(s)
        Gui.updateGui()
        if count[0] >= frames:
            if glide:
                view.fitAll()
            log(f"camera turn finished ({frames} interpolated frames)")
            on_done()
        else:
            QtCore.QTimer.singleShot(33, tick)

    tick()


def _outward(faces, box, whole):
    """Direction the feature faces towards: the area-weighted mean face normal, or (for a hole, whose wall
    normals cancel out) the direction from the part's centre to the feature."""
    total, acc = 0.0, App.Vector(0, 0, 0)
    for f in faces:
        try:
            u0, u1, v0, v1 = f.ParameterRange
            n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        except Exception:                                          # noqa: BLE001
            continue
        acc += n * f.Area
        total += f.Area
    if total > 0 and acc.Length > 0.3 * total:
        return acc * (1 / acc.Length)
    d = box.Center - whole.Center
    return d * (1 / d.Length) if d.Length > 1e-6 else None


def glide_to_box(box, then, ms=700, faces=None):
    """Smoothly zoom the camera onto `box` (a feature); a little room is left around it. If `faces` (the
    feature) point away from the camera, the view is also turned so that its side is seen. `then()` runs
    when the glide is done."""
    view = Gui.activeDocument().activeView()
    try:
        text, start_pos, start_h = _read_cam(view)
        start_rot = view.getCameraOrientation()
        back = start_rot.multVec(App.Vector(0, 0, 1))             # from the scene towards the camera
        end_rot = start_rot
        whole = state["obj"].Shape.BoundBox
        out = _outward(faces, box, whole) if faces else None
        if out is not None and out.dot(back) < 0.3:               # hidden or seen edge-on: turn to it
            if out.dot(back) < -0.99:
                turn = App.Rotation(start_rot.multVec(App.Vector(0, 1, 0)), 180)
            else:
                turn = App.Rotation(back, out)
            end_rot = turn.multiply(start_rot)
        log(f"feature faces {out} , camera back {back} -> {'turn' if end_rot is not start_rot else 'no turn'}")
        radius = max(box.DiagonalLength / 2, 1.0) * 1.6           # room around the feature
        d0 = abs((start_pos - whole.Center).dot(back))
        start_focus = start_pos - back * d0
        if start_h is not None:                                   # orthographic camera
            end_h = min(start_h, max(2 * radius, 0.1 * start_h))
            end_d = d0
        else:                                                     # perspective camera
            m = re.search(r"heightAngle\s+(\S+)", text)
            half = float(m.group(1)) / 2 if m else 0.3927
            end_h = None
            end_d = min(d0, max(radius / math.tan(half), 0.1 * d0))
    except Exception as e:                                         # noqa: BLE001
        log(f"zoom to feature unavailable ({e!r})")
        return then()
    turning = end_rot is not start_rot
    if turning:
        ms = max(ms, 1000)
    frames, count = max(1, ms // 33), [0]

    def tick():
        count[0] += 1
        s = count[0] / frames
        s = s * s * (3 - 2 * s)
        rot = start_rot.slerp(end_rot, s) if turning else start_rot
        focus = start_focus + (box.Center - start_focus) * s
        dist = d0 * (1 - s) + end_d * s
        pos = focus + rot.multVec(App.Vector(0, 0, dist))
        _write_cam(view, text, pos, None if end_h is None else start_h * (1 - s) + end_h * s,
                   rot if turning else None)
        Gui.updateGui()
        if count[0] >= frames:
            then()
        else:
            QtCore.QTimer.singleShot(33, tick)

    tick()


def snapshot(tag):
    Gui.updateGui()
    path = os.path.join(WORKDIR, "snapshots", f"{state['job']['name']}_{state['n']:02d}_{tag}.png")
    Gui.activeDocument().activeView().saveImage(path, 1100, 700, "White")
    state["n"] += 1


def window_snapshot(tag):
    """Whole FreeCAD window including the banner (the 3D view's saveImage doesn't capture overlays)."""
    Gui.updateGui()
    path = os.path.join(WORKDIR, "snapshots", f"{state['job']['name']}_{state['n']:02d}_{tag}.png")
    main = Gui.getMainWindow()
    # Screen capture (not widget.grab()): grab() renders the OpenGL 3D view as empty.
    QtGui.QGuiApplication.primaryScreen().grabWindow(main.winId()).save(path)
    state["n"] += 1


def start(index):
    if index >= len(jobs):
        if AUTOQUIT:
            QtCore.QTimer.singleShot(800, lambda: Gui.getMainWindow().close())
        return
    job = jobs[index]
    state.clear()
    state.update(index=index, job=job, n=0, failed=set(), phase="view", removed=0, failures=[],
                 sel=set(), auto=set(), history=[], busy=False, warned=set(), warning=False)
    open(os.path.join(WORKDIR, "logs", f"{job['name']}.log"), "w").close()
    hide_banner()
    hide_legend()

    doc = App.newDocument(job["name"])
    obj = doc.addObject("Part::Feature", "Model")
    obj.Shape = Part.read(job["file"])
    obj.Label = "After (defeatured)"
    # Static BEFORE copy to the left, so original and result are visible together (FR-VAL-02). The working
    # shape stays at the origin, so no exported coordinates change.
    before = doc.addObject("Part::Feature", "Before")
    before.Shape = obj.Shape.copy()
    before.Label = "Before (original)"
    # Isometric view: moving along (-X,-Y) is exactly "left on screen", so the two shapes sit side by side.
    bb = obj.Shape.BoundBox
    shift = max(0.62 * (bb.XLength + bb.YLength), 1.1 * max(bb.XLength, bb.YLength))
    before.Placement = App.Placement(App.Vector(-shift, -shift, 0), App.Rotation())
    doc.recompute()
    state["source"] = obj.Shape
    state["faces0"], state["vol0"] = len(obj.Shape.Faces), obj.Shape.Volume if obj.Shape.Solids else 0.0
    state["doc"], state["obj"], state["vo"], state["before"] = doc, obj, obj.ViewObject, before
    state["vo"].DisplayMode = "Flat Lines"
    before.ViewObject.DisplayMode = "Flat Lines"
    before.ViewObject.Visibility = False  # only revealed on the result screen, after the live removal
    log(f"START {job['name']} rules={job['rules']} faces={len(obj.Shape.Faces)}")

    def refocus(i):
        if state.get("index") == i and ensure_active():
            declutter()
            fit_view(iso=state.get("phase") in ("view", "fit2", "show", "orig", "select"))

    for delay in (400, 1500, 3000, 5000, 8000):  # the Start page may appear a few seconds after launch
        QtCore.QTimer.singleShot(delay, lambda i=index: refocus(i))
    QtCore.QTimer.singleShot(900, interactive_begin if INTERACTIVE else step)


def finish():
    job, shape = state["job"], state["obj"].Shape
    out_path = os.path.join(WORKDIR, "samples", "examples", "out", f"{job['name']}_gui_defeatured.step")
    shape.exportStep(out_path)
    matches_expected = None
    if "expected_faces" in job:
        matches_expected = (len(shape.Faces) == job["expected_faces"]
                             and abs(shape.Volume - job["expected_volume"]) <= 0.05)
    log(f"DONE faces={len(shape.Faces)} valid={shape.isValid()} volume={shape.Volume:.3f} "
        f"expected_match={matches_expected}")

    failures = state["failures"]
    if failures:  # same files and format as run_headless.py (FR-DEF-04 / NFR-REL-02)
        state["source"].exportStep(os.path.join(FAIL_DIR, f"{job['name']}_failed.step"))
        json.dump(failures, open(os.path.join(FAIL_DIR, f"{job['name']}_failed.json"), "w"), indent=1)
    summary = f"RESULT: {state['removed']} feature(s) removed, {len(failures)} failed"
    if failures:
        summary += f" - failure info saved to failures/{job['name']}_failed.json"

    index, doc_name = state["index"], state["doc"].Name
    last = index + 1 >= len(jobs)

    def next_job():
        App.closeDocument(doc_name)
        start(index + 1)

    def show_result():
        declutter()
        snapshot("compare")
        window_snapshot("summary")
        if INTERACTIVE:
            state["phase"], state["busy"], state["next_job"] = "result", False, next_job
            show_legend("RESULT: LEFT = BEFORE (red = selected), RIGHT = AFTER   |   \u2192 next example   "
                        "\u2190 back one step" if not last else
                        "RESULT: LEFT = BEFORE (red = selected), RIGHT = AFTER   |   \u2190 back one step   "
                        "(last example)")
            return
        if failures and last and not AUTOQUIT:
            return  # keep the result on screen; closing it would look like a crash
        QtCore.QTimer.singleShot(FAIL_HOLD_MS if failures else DELAY_MS, next_job)

    # Result screen: reveal the original next to the result and turn to an overview angle. If a failed face
    # points down it would be hidden in the usual top-down isometric view, so look from below instead
    # (flipping the camera about its horizontal axis keeps the two shapes side by side).
    paint_before()
    before_vo = state["before"].ViewObject
    before_vo.Transparency = 100  # starts invisible and fades in during the camera move
    before_vo.Visibility = True
    show_banner(summary, BANNER_FAIL if failures else BANNER_OK)
    show_legend("LEFT: BEFORE (original, red = selected for removal)   |   "
                "RIGHT: AFTER (defeatured result, orange = removal failed)")
    show_swatch(False)
    show_result_counter()
    after_box = App.BoundBox(shape.BoundBox)
    both_box = App.BoundBox(after_box)
    both_box.add(state["before"].Shape.BoundBox)

    def fade(t):
        before_vo.Transparency = int(round(100 * (1 - t)))
        text_alpha = min(1.0, max(0.0, (t - 0.4) / 0.6))  # messages appear in the second half of the move
        _set_opacity(_banner["label"], text_alpha * UI_ALPHA)
        _set_opacity(_legend["label"], text_alpha * UI_ALPHA)

    fade(0.0)
    failed_faces = [f for f in shape.Faces if core.sig(f) in state["failed"]]
    flip = any(core.normal(f) is not None and core.normal(f).z < -0.5 for f in failed_faces)

    def result_view(view):
        view.viewIsometric()
        if flip:
            view.setCameraOrientation(view.getCameraOrientation().multiply(
                App.Rotation(App.Vector(1, 0, 0), 180)))

    animate_view(result_view, show_result, ms=1600, on_frame=fade, centers=(after_box.Center, both_box.Center))


def step():
    current = state["obj"].Shape
    ensure_active()
    view = Gui.activeDocument().activeView()

    if state["phase"] in ("view", "fit2"):
        view.viewIsometric()
        view.fitAll()
        Gui.updateGui()
        state["phase"] = "fit2" if state["phase"] == "view" else "show"
        return QtCore.QTimer.singleShot(900, step)

    if state["phase"] == "show":
        paint()
        paint_before()
        snapshot("highlight")
        feature_groups = core.groups(current, core.select(current, state["job"]["rules"]))
        log(f"HIGHLIGHT {sum(len(g) for g in feature_groups)} faces red "
            f"in {len(feature_groups)} feature group(s)")
        try:
            highlight_path = os.path.join(WORKDIR, "samples", "examples", "highlight",
                                           f"{state['job']['name']}_highlight.step")
            ImportGui.export([state["obj"]], highlight_path)
            text = open(highlight_path, errors="ignore").read()
            log(f"colored STEP export (GUI mode): COLOUR_RGB={text.count('COLOUR_RGB')}")
        except Exception as e:
            log(f"colored export FAILED: {e!r}")
        state["phase"] = "remove"
        return QtCore.QTimer.singleShot(DELAY_MS, step)

    feature_groups = core.groups(current, core.select(current, state["job"]["rules"], state["failed"]))
    if not feature_groups:
        paint()
        snapshot("final")
        return finish()

    group = feature_groups[0]
    kinds = ",".join(sorted({type(f.Surface).__name__ for f in group}))
    ok, new_shape, why = core.remove_group(current, group)
    if ok:
        state["obj"].Shape = new_shape
        state["doc"].recompute()
        state["removed"] += 1
        log(f"REMOVED feature ({len(group)} faces: {kinds}): "
            f"faces {len(current.Faces)}->{len(new_shape.Faces)} volume={new_shape.Volume:.2f}")
        paint()
        snapshot("removed")
    else:
        state["failed"].update(core.sig(f) for f in group)
        state["failures"].append({"faces": len(group), "types": sorted({type(f.Surface).__name__ for f in group}),
                                  "sigs": [core.sig(f) for f in group], "reason": why})
        log(f"FAILED feature ({len(group)} faces: {kinds}): {why} -> kept, geometry+face IDs stored")
        paint()
        snapshot("failed")
        show_banner(f"REMOVAL FAILED: {len(group)} face(s) ({kinds}) could not be removed ({why}). "
                    f"The failed face is orange. Original geometry kept; geometry + face IDs saved for manual correction.",
                    BANNER_FAIL)

        def after_turn():
            window_snapshot("failed_banner")
            QtCore.QTimer.singleShot(FAIL_HOLD_MS, step)

        set_target = face_view_fn(group[0])
        return animate_view(set_target, after_turn) if set_target else after_turn()
    QtCore.QTimer.singleShot(DELAY_MS, step)


# ----------------------------------------------------------------------------------------------------
# Interactive mode: arrow keys step through the demo; clicking a face adds it to / removes it from the
# selection; a live counter (bottom right) shows what is selected.
# ----------------------------------------------------------------------------------------------------
_counter = {}


def show_counter(html):
    _counter["hidden"] = False
    main = Gui.getMainWindow()
    if "label" not in _counter:
        label = MessageLabel(main, "counter")
        label.setTextFormat(QtCore.Qt.RichText)
        label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        label.setStyleSheet("background:rgba(0,0,0,190); color:white; font-size:16px; padding:8px 40px 8px 12px;")
        _counter["label"] = label
    label = _counter["label"]
    label.setText(html)
    _counter["html"] = html
    _set_opacity(label, UI_ALPHA)
    area = main.centralWidget()
    origin = area.mapTo(main, QtCore.QPoint(0, 0))
    label.setFixedSize(label.sizeHint())                      # size to the text incl. the padding left for the X
    label.move(origin.x() + area.width() - label.width() - 20, origin.y() + area.height() - 94 - label.height())
    _close_button(label, "counter")
    if _shown("counter"):
        label.show()
        label.raise_()


def _refresh_counter():
    if "html" in _counter and not _counter.get("hidden"):
        show_counter(_counter["html"])


def hide_counter():
    _counter["hidden"] = True
    if "label" in _counter:
        _counter["label"].hide()


def _guard(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:                              # noqa: BLE001
            import traceback
            state["busy"] = False
            log("ERROR in " + fn.__name__ + ":\n" + traceback.format_exc())
            show_banner(f"Internal error in {fn.__name__} - see logs/{state['job']['name']}.log", BANNER_FAIL, 64)
    wrapper.__name__ = fn.__name__
    return wrapper


def sel_faces(shape):
    return [f for f in shape.Faces if core.sig(f) in state["sel"] and core.sig(f) not in state["failed"]]


def paint_sel():
    shape = state["obj"].Shape
    def color(f):
        s = core.sig(f)
        if s in state["failed"]:
            return ORANGE
        if s in state["sel"]:
            return RED if s in state["auto"] else ORANGE   # orange: selected by hand, outside the rules
        return GRAY

    state["vo"].DiffuseColor = [color(f) for f in shape.Faces]
    Gui.updateGui()


VOLUME_WARN = 5.0      # percent: a bigger volume change is flagged (a structural face may have been removed)


def _table(title, rows, title_color="#ffffff"):
    """HTML for the counter: a title and label / value rows. rows: (label, value, color or None)."""
    body = "".join(
        f"<tr><td style='color:#bbbbbb; padding-right:18px;'>{label}</td>"
        f"<td align='right' style='color:{color or '#ffffff'};'><b>{value}</b></td></tr>"
        for label, value, color in rows)
    return (f"<table cellspacing='2'><tr><td colspan='2' style='color:{title_color};'><b>{title}</b></td></tr>"
            f"{body}</table>")


def _volume_row(shape):
    if not shape.Solids or not state.get("vol0"):
        return ("Volume", "n/a (surface model)", None)
    change = (shape.Volume - state["vol0"]) / state["vol0"] * 100
    if abs(change) >= VOLUME_WARN:
        return ("Volume", f"{change:+.1f} %  \u26a0 check", "#ffb347")
    return ("Volume", f"{change:+.1f} %", None)


def update_counter():
    shape = state["obj"].Shape
    faces = sel_faces(shape)
    n = len(faces)
    added, removed = len(state["sel"] - state["auto"]), len(state["auto"] - state["sel"])
    outside = len({core.sig(f) for f in faces} - state["auto"])
    if state["phase"] == "select":
        features = len(core.groups(shape, faces)) if len(shape.Faces) <= 400 and faces else ("-" if faces else 0)
        show_counter(_table("REMOVAL SELECTION", [
            ("To remove", f"{n} faces \u00b7 {features} features", None),
            ("Edited by you", f"+{added} added \u00b7 \u2212{removed} removed", "#7CFC00" if added or removed else None),
            *([("Outside the rules", f"{outside} faces", "#ffb347")] if outside else []),
            ("Model", f"{len(shape.Faces)} faces", None)]))
    elif state["phase"] == "removing":
        if len(shape.Faces) <= 400:      # the total follows clicks made while the steps run
            state["total"] = state["removed"] + len(state["failures"]) + (len(core.groups(shape, faces)) if faces else 0)
        total, done = max(state["total"], 1), state["removed"] + len(state["failures"])
        dots = "\u25cf" * min(done, total) + "\u25cb" * max(total - done, 0)
        failed = len(state["failures"])
        show_counter(_table(f"REMOVING  {dots}  {done} of {state['total']}", [
            ("Faces", f"{state['faces0']} \u2192 {len(shape.Faces)}  ({len(shape.Faces) - state['faces0']:+d})", None),
            _volume_row(shape),
            ("Failed", str(failed), "#ffb347" if failed else None),
            ("Still selected", f"{n} faces", None)]))


def show_result_counter():
    shape = state["obj"].Shape
    f0, f1 = state["faces0"], len(shape.Faces)
    failed = len(state["failures"])
    show_counter(_table("RESULT", [
        ("Faces", f"{f0} \u2192 {f1}  ({(f1 - f0) / f0 * 100:+.0f} %)", None),
        _volume_row(shape),
        ("Features", f"{state['removed']} removed \u00b7 {failed} failed", "#ffb347" if failed else None)]))


# colour key (bottom left): what red / orange / grey mean
_swatch = {}


def show_swatch(visible=True):
    main = Gui.getMainWindow()
    if "label" not in _swatch:
        label = MessageLabel(main, "swatch")
        label.setTextFormat(QtCore.Qt.RichText)
        label.setStyleSheet("background:rgba(0,0,0,170); color:white; font-size:15px; padding:6px 40px 6px 12px;")
        _swatch["label"] = label
    label = _swatch["label"]
    label.setText("<span style='color:#d91f1f;'>\u25a0</span> selected for removal &nbsp;&nbsp;"
                  "<span style='color:#ff8c00;'>\u25a0</span> outside the rules / removal failed &nbsp;&nbsp;"
                  "<span style='color:#bfc7d1;'>\u25a0</span> kept")
    _set_opacity(label, UI_ALPHA)
    area = main.centralWidget()
    origin = area.mapTo(main, QtCore.QPoint(0, 0))
    label.setFixedSize(label.sizeHint())
    label.move(origin.x() + 20, origin.y() + area.height() - 94 - label.height())
    if visible and "swatch" not in _dismissed:
        label.show()
        label.raise_()
    else:
        label.hide()


def interactive_begin():
    state["phase"] = "orig"
    fit_view(iso=True)
    state["vo"].DiffuseColor = [GRAY] * len(state["obj"].Shape.Faces)
    show_banner(f"{state['job']['name']}: ORIGINAL model  -  press \u2192 to run the automatic selection", BANNER_STEP, 64)
    show_legend("\u2192 next    \u2190 back    H hide messages")
    show_swatch(False)
    hide_counter()
    window_snapshot("original")


def go_select():
    shape = state["obj"].Shape
    if not state["auto"] and not state["sel"]:
        picked = core.select(shape, state["job"]["rules"])
        state["auto"] = {core.sig(f) for f in picked}
        state["sel"] = set(state["auto"])
        log(f"AUTO-SELECTION {len(state['auto'])} faces")
    state["phase"] = "select"
    paint_sel()
    paint_before()
    show_banner("AUTOMATIC SELECTION (red)  -  click a face to ADD it, click a red face to REMOVE it, "
                "then press \u2192 to remove the red faces", BANNER_STEP, 64)
    show_legend("Click: add / remove a face    \u2192 start removal    \u2190 back    R reset    H hide messages")
    show_swatch(True)
    update_counter()
    window_snapshot("selection")


@_guard
def toggle_face(index):
    """index: 1-based face number, as in the 'FaceN' name the 3D view reports for a click."""
    shape = state["obj"].Shape
    if state.get("phase") not in ("select", "removing") or state.get("busy") or not 1 <= index <= len(shape.Faces):
        return
    sig = core.sig(shape.Faces[index - 1])
    if sig in state["sel"]:
        state["sel"].discard(sig)
        log(f"CLICK face {index}: removed from the selection")
    else:
        state["sel"].add(sig)
        log(f"CLICK face {index}: added to the selection")
    paint_sel()
    if state["warning"]:
        pending = override_sigs()
        if pending:
            show_override_warning(pending)
        else:                               # the faces outside the rules were deselected: no warning needed
            state["warning"] = False
            phase_banner()
    update_counter()


def reset_selection():
    if state.get("phase") == "select":
        state["sel"] = set(state["auto"])
        state["warning"] = False
        phase_banner()
        paint_sel()
        update_counter()
        log("selection reset to the automatic one")


def begin_removal():
    shape = state["obj"].Shape
    faces = sel_faces(shape)
    if not faces:
        show_banner("Nothing is selected - click a face to select it first", BANNER_FAIL)
        return
    groups = core.groups(shape, faces)
    state.update(phase="removing", total=len(groups))
    log(f"HIGHLIGHT {len(faces)} faces red in {len(groups)} feature group(s)")
    paint_before()
    state["history"] = []
    remove_next()


def remove_next():
    current = state["obj"].Shape
    faces = sel_faces(current)
    groups = core.groups(current, faces) if faces else []
    if not groups:
        paint_sel()
        snapshot("final")
        state["busy"] = True
        whole = state["obj"].Shape.BoundBox
        return glide_to_box(whole, finish, ms=500)      # zoom back out, then the before / after screen
    group = groups[0]
    box = App.BoundBox()
    for f in group:
        box.add(f.BoundBox)
    state["busy"] = True

    def after_zoom():
        state["busy"] = False
        _remove_group(current, group)

    glide_to_box(box, _guard(after_zoom), faces=group)


def _remove_group(current, group):
    state["history"].append((current, set(state["failed"]), list(state["failures"]), state["removed"]))
    kinds = ",".join(sorted({type(f.Surface).__name__ for f in group}))
    ok, new_shape, why = core.remove_group(current, group)
    if ok:
        state["obj"].Shape = new_shape
        state["doc"].recompute()
        state["removed"] += 1
        log(f"REMOVED feature ({len(group)} faces: {kinds}): "
            f"faces {len(current.Faces)}->{len(new_shape.Faces)} volume={new_shape.Volume:.2f}")
        paint_sel()
        snapshot("removed")
        show_banner(f"Feature {state['removed']} of {state['total']} removed ({len(group)} faces: {kinds})"
                    f"  -  press \u2192 for the next step", BANNER_STEP, 64)
        show_legend("\u2192 next    \u2190 undo    Click: add / remove a face    H hide messages")
        update_counter()
        return
    state["failed"].update(core.sig(f) for f in group)
    state["failures"].append({"faces": len(group), "types": sorted({type(f.Surface).__name__ for f in group}),
                              "sigs": [core.sig(f) for f in group], "reason": why})
    log(f"FAILED feature ({len(group)} faces: {kinds}): {why} -> kept, geometry+face IDs stored")
    paint_sel()
    snapshot("failed")
    show_banner(f"REMOVAL FAILED: {len(group)} face(s) ({kinds}) could not be removed ({why}). "
                f"The failed face is orange. Original geometry kept; geometry + face IDs saved for manual correction.",
                BANNER_FAIL)
    show_legend("\u2192 next    \u2190 undo    Click: add / remove a face    H hide messages")
    update_counter()
    state["busy"] = True

    def after_turn():
        window_snapshot("failed_banner")
        state["busy"] = False

    set_target = face_view_fn(group[0])
    animate_view(set_target, after_turn) if set_target else after_turn()


@_guard
def go_back():
    phase = state.get("phase")
    if state.get("busy"):
        return
    state["warning"] = False
    if phase == "select":
        state["phase"] = "orig"
        interactive_begin()
    elif phase in ("removing", "result"):
        if phase == "result":
            state["before"].ViewObject.Visibility = False
            hide_legend()
            state["phase"] = "removing"
        if state["history"]:
            shape, failed, failures, removed = state["history"].pop()
            state["obj"].Shape = shape
            state["doc"].recompute()
            state["failed"], state["failures"], state["removed"] = failed, failures, removed
            paint_sel()
            fit_view(iso=True)
            show_banner("Step undone  -  press \u2192 to redo it, \u2190 to undo more", BANNER_STEP, 64)
            show_legend("\u2192 next    \u2190 undo    Click: add / remove a face    H hide messages")
            update_counter()
        else:
            go_select()
            fit_view(iso=True)


BANNER_WARN = "#b35900"


def override_sigs():
    """Selected faces of the current model that the rules did not select and the user has not yet been warned about."""
    shape = state["obj"].Shape
    return {core.sig(f) for f in sel_faces(shape)} - state["auto"] - state["warned"]


def phase_banner():
    """The normal message of the current phase (after a warning went away)."""
    if state["phase"] == "select":
        show_banner("AUTOMATIC SELECTION (red)  -  click a face to ADD it, click a red face to REMOVE it, "
                    "then press \u2192 to remove the red faces", BANNER_STEP, 64)
    elif state["phase"] == "removing":
        show_banner(f"Removed {state['removed']} of {state['total']} feature(s)  -  press \u2192 for the next step",
                    BANNER_STEP, 64)


def show_override_warning(pending):
    state["warning"] = True
    show_banner(f"\u26a0 WARNING: {len(pending)} selected face(s) are NOT selected by the rules (orange). "
                f"Removing them can change the part. Click an orange face to deselect it, "
                f"or press \u2192 again to continue anyway.", BANNER_WARN, 78)
    log(f"WARNING shown: {len(pending)} face(s) outside the rules")


def override_gate():
    """True if the step must wait: the first press with faces outside the rules only shows the warning;
    pressing again accepts them (the warning goes away) and the work continues."""
    if state["phase"] not in ("select", "removing"):
        return False
    pending = override_sigs()
    if not pending:
        return False
    if not state["warning"]:
        show_override_warning(pending)
        return True
    state["warned"] |= pending
    state["warning"] = False
    log(f"WARNING accepted: continuing with {len(pending)} face(s) outside the rules")
    phase_banner()
    return False


@_guard
def go_next():
    phase = state.get("phase")
    if state.get("busy"):
        return
    if override_gate():
        return
    if phase == "orig":
        go_select()
    elif phase == "select":
        begin_removal()
    elif phase == "removing":
        remove_next()
    elif phase == "result":
        state["next_job"]()


class _Keys(QtCore.QObject):
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress and state.get("phase"):
            key = event.key()
            if event.isAutoRepeat():       # a held key must not run through all the steps
                return key in (QtCore.Qt.Key_Right, QtCore.Qt.Key_Down, QtCore.Qt.Key_Space,
                               QtCore.Qt.Key_Return, QtCore.Qt.Key_Left, QtCore.Qt.Key_Up, QtCore.Qt.Key_Backspace)
            if key in (QtCore.Qt.Key_Right, QtCore.Qt.Key_Down, QtCore.Qt.Key_Space, QtCore.Qt.Key_Return):
                go_next()
                return True
            if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Up, QtCore.Qt.Key_Backspace):
                go_back()
                return True
            if key == QtCore.Qt.Key_R:
                reset_selection()
                return True
            if key == QtCore.Qt.Key_H:
                toggle_messages()
                return True
        return False


class _Picker:
    """Selection observer: a click on a face of our model toggles it in the selection."""

    def addSelection(self, doc, obj, sub, pnt):
        if state.get("phase") not in ("select", "removing") or doc != state["doc"].Name or obj != state["obj"].Name:
            return
        if sub.startswith("Face"):
            try:
                toggle_face(int(sub[4:]))
            finally:
                Gui.Selection.clearSelection()


if INTERACTIVE:
    _keys = _Keys()
    QtWidgets.QApplication.instance().installEventFilter(_keys)
    _picker = _Picker()
    Gui.Selection.addObserver(_picker)

    # unattended test of the interactive mode: CLEANCAD_TEST_SEQ="n,n,t:5,n,b,..." (n next, b back,
    # t:K toggle face K, r reset), one action every 2.5 s
    _seq = [s for s in os.environ.get("CLEANCAD_TEST_SEQ", "").split(",") if s]

    def _run_seq():
        if not _seq:
            return
        if state.get("busy"):
            return QtCore.QTimer.singleShot(800, _run_seq)
        action = _seq.pop(0)
        if action == "n":
            go_next()
        elif action == "b":
            go_back()
        elif action == "r":
            reset_selection()
        elif action.startswith("t:"):
            toggle_face(int(action[2:]))
        QtCore.QTimer.singleShot(2500, lambda: (window_snapshot(f"seq_{action.replace(':', '')}"), _run_seq()))

    if _seq:
        QtCore.QTimer.singleShot(6000, _run_seq)


start(0)
