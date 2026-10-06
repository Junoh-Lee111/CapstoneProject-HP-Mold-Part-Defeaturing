"""Live FreeCAD GUI demo of the CleanCAD prototype: highlights faces selected for removal in
red, then removes them feature-by-feature with the 3D view updating in real time.

Run inside FreeCAD's GUI (see fcdemo.sh), not with FreeCADCmd.

Jobs come from $CLEANCAD_WORKDIR/samples/examples/manifest.json (all examples, or a subset
via CLEANCAD_ONLY=name1,name2), or a single external file via CLEANCAD_INPUT + CLEANCAD_RULE.
All results (STEP, snapshots, logs) are written under $CLEANCAD_WORKDIR - nothing in the repo.
"""
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleancad_core as core

DELAY_MS = int(os.environ.get("CLEANCAD_DELAY_MS", "1200"))
FAIL_HOLD_MS = int(os.environ.get("CLEANCAD_FAIL_HOLD_MS", "4500"))
AUTOQUIT = os.environ.get("CLEANCAD_AUTOQUIT") == "1"
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
    ctx = core.Ctx(src)
    fns = [core.RULES[r] for r in state["job"]["rules"]]
    state["before"].ViewObject.DiffuseColor = [
        RED if any(fn(f, ctx) for fn in fns) else GRAY for f in src.Faces]


_banner = {}
_legend = {}


def show_legend(text):
    main = Gui.getMainWindow()
    if "label" not in _legend:
        label = QtWidgets.QLabel(main)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("background:rgba(0,0,0,170); color:white; font-size:16px; padding:6px;")
        _legend["label"] = label
    label = _legend["label"]
    label.setText(text)
    _set_opacity(label, 1.0)
    area = main.centralWidget()
    origin = area.mapTo(main, QtCore.QPoint(0, 0))
    label.setGeometry(origin.x() + 20, origin.y() + area.height() - 84, area.width() - 40, 34)
    label.show()
    label.raise_()


def hide_legend():
    if "label" in _legend:
        _legend["label"].hide()


def show_banner(text, bg):
    """On-screen message over the 3D view, so a failure can't be mistaken for a crash."""
    main = Gui.getMainWindow()
    if "label" not in _banner:
        label = QtWidgets.QLabel(main)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignCenter)
        _banner["label"] = label
    label = _banner["label"]
    label.setStyleSheet(f"background:{bg}; color:white; font-size:20px; font-weight:bold; padding:10px;")
    label.setText(text)
    _set_opacity(label, 1.0)
    area = main.centralWidget()
    origin = area.mapTo(main, QtCore.QPoint(0, 0))
    label.setGeometry(origin.x() + 20, origin.y() + 12, area.width() - 40, 100)
    label.show()
    label.raise_()
    Gui.updateGui()


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


def fit_view(iso=False):
    view = Gui.activeDocument().activeView()
    if iso:
        view.viewIsometric()
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


def _write_cam(view, text, pos, height):
    text = re.sub(r"position\s+\S+\s+\S+\s+\S+", f"position {pos.x} {pos.y} {pos.z}", text, count=1)
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
    state.update(index=index, job=job, n=0, failed=set(), phase="view", removed=0, failures=[])
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
    state["doc"], state["obj"], state["vo"], state["before"] = doc, obj, obj.ViewObject, before
    state["vo"].DisplayMode = "Flat Lines"
    before.ViewObject.DisplayMode = "Flat Lines"
    before.ViewObject.Visibility = False  # only revealed on the result screen, after the live removal
    log(f"START {job['name']} rules={job['rules']} faces={len(obj.Shape.Faces)}")

    def refocus(i):
        if state.get("index") == i and ensure_active():
            fit_view(iso=state.get("phase") in ("view", "fit2", "show"))

    for delay in (400, 1500, 3000, 5000, 8000):  # the Start page may appear a few seconds after launch
        QtCore.QTimer.singleShot(delay, lambda i=index: refocus(i))
    QtCore.QTimer.singleShot(900, step)


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
        snapshot("compare")
        window_snapshot("summary")
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
    after_box = App.BoundBox(shape.BoundBox)
    both_box = App.BoundBox(after_box)
    both_box.add(state["before"].Shape.BoundBox)

    def fade(t):
        before_vo.Transparency = int(round(100 * (1 - t)))
        text_alpha = min(1.0, max(0.0, (t - 0.4) / 0.6))  # messages appear in the second half of the move
        _set_opacity(_banner["label"], text_alpha)
        _set_opacity(_legend["label"], text_alpha)

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


start(0)
