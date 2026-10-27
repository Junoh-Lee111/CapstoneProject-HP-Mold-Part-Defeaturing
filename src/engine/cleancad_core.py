"""CleanCAD core mechanics (runs inside FreeCAD, headless or GUI).

MECHANISM (stable): groups() / remove_group() / process()
CRITERIA (to be filled in by the team): the RULES registry below - "which faces to remove?"

The rules registered here are TEST SCAFFOLDING ONLY: simple stand-ins so the removal
mechanism can be exercised end to end. The real decision logic (Stage 1 rule-based,
Stage 2 ML-based per the confirmed architecture) plugs in the same way - register a
function with @rule("name") that takes (face, ctx) and returns True if that face
should be removed.
"""
import atexit
import json
import os
import shutil
import subprocess
import tempfile
import time

import FreeCAD
import Part

MAX_SMALL_RADIUS = 5.0
RULES = {}
SET_RULES = {}   # name -> fn(shape) -> list of faces (rules that need the whole shape, e.g. hole groups)
CATEGORY = {}    # rule name -> what it recognises: holes / edges / protrusions / markings / scaffolding
BATCH = {}       # name -> "try" | "only": remove ALL faces the rule selects in one operation
#                  ("try": fall back to per-feature removal on failure; "only": all-or-nothing)

# Size thresholds are configuration (the mentor: "should not be treated as a universal rule").
PROFILES = {
    # example parameters of the HP-supplied script (hard_7); NOT general criteria
    "hp_example": {"hole_diameter": 6.0, "fillet_radius": 10.0, "logo_max_depth": 0.5,
                   "boss_max_diameter": 20.0, "rib_max_thickness": 4.0, "chamfer_size": 5.0},
    # recognition-only evaluation: size limits so wide that no real feature is filtered out by size
    "recognition_only": {"hole_diameter": 50.0, "fillet_radius": 50.0, "logo_max_depth": 0.5,
                   "boss_max_diameter": 20.0, "rib_max_thickness": 4.0, "chamfer_size": 5.0},
    # HP: when fastener holes must be kept, remove only holes of 2 mm or less (fasteners are ~2.7 mm).
    # fillet value is the earlier mentor starting value, still to be confirmed.
    "keep_fasteners": {"hole_diameter": 2.0 + 1e-6, "fillet_radius": 5.0, "logo_max_depth": 0.5,
                   "boss_max_diameter": 20.0, "rib_max_thickness": 4.0, "chamfer_size": 5.0},
}
PROFILE = dict(PROFILES[os.environ.get("CLEANCAD_PROFILE", "hp_example")])


def set_profile(name):
    PROFILE.clear()
    PROFILE.update(PROFILES[name])


def rule(name, category="scaffolding"):
    def deco(fn):
        RULES[name] = fn
        CATEGORY[name] = category
        return fn
    return deco


# The order in which all rules are applied: stand-up features first (ribs and bosses carry root fillets that
# must not be removed on their own), then holes, then rounded / bevelled edges, then markings.
RULE_ORDER = ("protrusions", "holes", "edges", "markings")


def all_rules():
    """Every real rule (not the test scaffolding) in the order they should be applied."""
    cats = rules_by_category()
    return [r for cat in RULE_ORDER for r in cats.get(cat, [])]


def rules_by_category():
    """{category: [rule names]} - the rules grouped by what they recognise."""
    out = {}
    for name in RULES:
        out.setdefault(CATEGORY.get(name, "other"), []).append(name)
    return out


def set_rule(name, batch=None, category="other"):
    """Register a rule that selects faces by looking at the whole shape. It is exposed in RULES as
    a per-face predicate too (membership in the selection), so select()/the demo need no changes."""
    def deco(fn):
        SET_RULES[name] = fn
        CATEGORY[name] = category
        if batch:
            BATCH[name] = batch
        RULES[name] = lambda f, c: sig(f) in c.picked(name)
        return fn
    return deco


def sig(face):
    c = face.CenterOfMass
    return (type(face.Surface).__name__, round(face.Area, 3), round(c.x, 2), round(c.y, 2), round(c.z, 2))


def normal(face):
    try:
        return face.normalAt(*face.Surface.parameter(face.CenterOfMass))
    except Exception:
        return None


class Ctx:
    """Shared per-shape context available to rule functions (e.g. the base plate's top Z)."""

    def __init__(self, shape):
        self.shape = shape
        self._picked = {}
        ups = [f for f in shape.Faces if type(f.Surface).__name__ == "Plane"
               and (normal(f) is not None and normal(f).z > 0.99)]
        self.base_z = max(ups, key=lambda f: f.Area).CenterOfMass.z if ups else 0.0

    def picked(self, name):
        """Face signatures selected by a SET rule (computed once per Ctx)."""
        if name not in self._picked:
            self._picked[name] = {sig(f) for f in SET_RULES[name](self.shape)}
        return self._picked[name]


# ---------------- test-scaffolding rules (NOT the project's real decision criteria) ----------------
@rule("cyl")        # small cylinders: holes, small fillets
def _cyl(f, c):
    return type(f.Surface).__name__ == "Cylinder" and f.Surface.Radius <= MAX_SMALL_RADIUS


@rule("prot")       # faces protruding above the base plate: ribs, bosses, raised emboss
def _prot(f, c):
    bb = f.BoundBox
    return bb.ZMin >= c.base_z - 1e-6 and bb.ZMax > c.base_z + 1e-6


@rule("recess")     # faces sunk below the top surface (not the bottom/sides): pockets, engraved emboss
def _recess(f, c):
    bb = f.BoundBox
    return bb.ZMin > 1e-6 and bb.ZMin < c.base_z - 1e-6 and bb.ZMax <= c.base_z + 1e-6


@rule("chamfer")    # small inclined planes and cones
def _chamfer(f, c):
    t = type(f.Surface).__name__
    if t == "Cone":
        return f.Area < 200
    if t != "Plane":
        return False
    n = normal(f)
    return n is not None and max(abs(n.x), abs(n.y), abs(n.z)) < 0.99 and f.Area < 200


@rule("fail_demo")  # deliberately selects an un-removable face, to exercise failure handling
def _fail(f, c):
    return type(f.Surface).__name__ == "Plane" and f.BoundBox.ZMax < 1e-6
# ------------------------------------------------------------------------------------------------


def select(shape, rule_names, failed=()):
    ctx = Ctx(shape)
    fns = [RULES[r] for r in rule_names]
    return [f for f in shape.Faces if any(fn(f, ctx) for fn in fns) and sig(f) not in failed]


def groups(shape, faces):
    """Connected components of the selected faces: one physical feature each
    (e.g. a rib's 5 faces are removed together, not one at a time)."""
    all_faces = shape.Faces

    def idx(f):
        return next(i for i, g in enumerate(all_faces) if g.isSame(f))

    selected = {idx(f) for f in faces}
    if not selected:
        return []
    parent = {i: i for i in selected}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in shape.Edges:
        adjacent = [a for a in (idx(f) for f in shape.ancestorsOfType(e, Part.Face)) if a in selected]
        for a in adjacent[1:]:
            parent[find(a)] = find(adjacent[0])
    out = {}
    for i in selected:
        out.setdefault(find(i), []).append(all_faces[i])
    return list(out.values())


# FreeCAD's defeaturing() is one blocking C++ call: on some real (free-form) geometry it never
# returns, and neither a Python thread nor a forked child can interrupt it (OCCT's thread pool does
# not survive fork). Headless runs therefore send each removal to a separate worker process
# (src/engine/defeature_worker.py, one long-lived FreeCAD instance) and kill it after DEFEATURE_TIMEOUT
# seconds. A timeout (or a crash of the worker) is reported as an ordinary failure, so process()
# skips that feature and carries on (the limit is scaled up for models of more than 500 faces).
# In the GUI the call runs in-process without a limit.
DEFEATURE_TIMEOUT = float(os.environ.get("CLEANCAD_DEFEATURE_TIMEOUT", "60"))   # seconds; 0 = off


class WorkerUnavailable(Exception):
    pass


class _Worker:
    """One long-lived FreeCAD process that executes defeaturing requests."""

    def __init__(self):
        self.proc = None
        self.dir = None
        self.n = 0

    def _start(self):
        self.dir = tempfile.mkdtemp(prefix="cleancad_worker_")
        exe = os.path.join(FreeCAD.getHomePath(), "bin", "freecadcmd")
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "defeature_worker.py")
        if not (os.path.exists(exe) and os.path.exists(script)):
            raise WorkerUnavailable("freecadcmd or defeature_worker.py not found")
        env = dict(os.environ, CLEANCAD_WORKER_DIR=self.dir, CLEANCAD_PARENT_PID=str(os.getpid()))
        self.proc = subprocess.Popen([exe, script], env=env, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        deadline = time.monotonic() + 120
        while not os.path.exists(os.path.join(self.dir, "ready")):
            if self.proc.poll() is not None or time.monotonic() > deadline:
                self.kill()
                raise WorkerUnavailable("worker did not start")
            time.sleep(0.05)

    def kill(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
        if self.proc is not None:
            self.proc.wait()
        self.proc = None
        if self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)
            self.dir = None
        self.n = 0

    def run(self, shape, group, timeout, delay=0, tool=None):
        """-> ("ok", result dict incl. 'brep') | ("timeout"|"crash"|"error", message).
        With `tool` the worker cuts that shape away instead of calling defeaturing()."""
        if self.proc is None or self.proc.poll() is not None:
            self.kill()
            self._start()
        faces = list(shape.Faces)
        idx = [next(i for i, f in enumerate(faces) if f.isSame(g)) for g in group]
        self.n += 1
        n = self.n

        def put(name, text):
            with open(os.path.join(self.dir, name + ".tmp"), "w") as fh:
                fh.write(text)
            os.rename(os.path.join(self.dir, name + ".tmp"), os.path.join(self.dir, name))

        put(f"req{n}.brep", shape.exportBrepToString())
        if tool is not None:
            put(f"req{n}.tool.brep", tool.exportBrepToString())
        put(f"req{n}.json", json.dumps({"faces": idx, "delay": delay, "op": "cut" if tool is not None else "defeature"}))
        res_path = os.path.join(self.dir, f"res{n}.json")
        deadline = time.monotonic() + timeout
        while not os.path.exists(res_path):
            if self.proc.poll() is not None:
                self.kill()
                return "crash", "the CAD kernel process died"
            if time.monotonic() > deadline:
                self.kill()
                return "timeout", f"no answer after {timeout:g} s"
            time.sleep(0.01)
        res = json.load(open(res_path))
        if "error" in res:
            return "error", res["error"]
        res["brep"] = open(os.path.join(self.dir, f"res{n}.brep")).read()
        return "ok", res


FALLBACKS = []   # fn(shape, group) -> tool shape to cut away, or None: tried when defeaturing() does nothing


def removal_fallback(fn):
    FALLBACKS.append(fn)
    return fn


_WORKER = _Worker()
atexit.register(_WORKER.kill)


def _judge(group, new_shape):
    """Facts about a defeaturing result, as a plain dict."""
    after = list(new_shape.Faces)
    return {"faces": len(after), "volume": new_shape.Volume, "valid": new_shape.isValid(),
            "gone": [not any(f.isSame(a) for a in after) for f in group]}


def _attempt(shape, group, timeout, delay=0, tool=None):
    """One removal attempt (defeaturing, or cutting `tool` away). -> (state, new_shape, result dict | message)"""
    if timeout > 0 and not FreeCAD.GuiUp:
        try:
            state, res = _WORKER.run(shape, group, timeout, delay, tool)
        except WorkerUnavailable:
            state = "inprocess"          # no worker possible here: run unguarded
        if state != "inprocess":
            if state != "ok":
                return state, None, res
            new_shape = Part.Shape()
            new_shape.importBrepFromString(res["brep"])
            return "ok", new_shape, res
    new_shape = shape.defeaturing(group) if tool is None else shape.cut(tool).removeSplitter()
    return "ok", new_shape, _judge(group, new_shape)


def remove_group_ex(shape, group, timeout=None, _test_delay=0):
    """Remove one feature (a group of connected faces).

    FreeCAD's defeaturing fails SILENTLY when a face can't be removed - it just
    returns the shape unchanged. Success must therefore be judged by comparing
    the result to the input, not by catching an exception. When defeaturing() does nothing, raises or
    times out, the registered FALLBACKS may take over: each gets (shape, group) and returns None, a tool
    shape to cut away (e.g. the prism above a rib), or ("result", new_shape) it built itself.

    Returns (ok, shape, why, gone) where gone[i] says whether group[i] no longer exists in the result.
    """
    if timeout is None:
        # a big model legitimately needs longer (a 1000-face logo takes ~35 s): the limit grows with the face
        # count above 500 faces, so only a genuinely stuck kernel call is cut off
        timeout = DEFEATURE_TIMEOUT * max(1.0, len(shape.Faces) / 500.0)
    nothing = [False] * len(group)

    def changed(res):
        return res["faces"] < len(shape.Faces) or abs(res["volume"] - shape.Volume) > 1e-6

    try:
        state, new_shape, res = _attempt(shape, group, timeout, _test_delay)
        failure = None                                  # why the first attempt did not work
        if state == "timeout":
            failure = f"timeout ({res})"
        elif state == "crash":
            failure = f"crash ({res})"
        elif state == "error":
            failure = f"exception: {res}"
        elif not changed(res):
            failure = "no-op (shape unchanged)"
        how = ""
        if failure:
            for fallback in FALLBACKS:
                proposal = fallback(shape, group)
                if proposal is None:
                    continue
                if isinstance(proposal, tuple) and proposal[0] == "result":
                    state2, new2, res2 = "ok", proposal[1], _judge(group, proposal[1])
                    how2 = " (rebuilt)"
                else:
                    state2, new2, res2 = _attempt(shape, group, timeout, 0, proposal)
                    how2 = " (boolean cut)"
                if state2 == "ok" and changed(res2):
                    new_shape, res, failure, how = new2, res2, None, how2
                    break
            if failure:
                gone = res["gone"] if state == "ok" else nothing
                return False, shape, failure, gone
    except Exception as e:                   # noqa: BLE001
        return False, shape, f"exception: {e!r}", nothing
    if not res["valid"]:
        return False, shape, "result invalid", res["gone"]
    return True, new_shape, "ok" + how, res["gone"]


def remove_group(shape, group):
    """remove_group_ex() without the per-face `gone` flags: (ok, shape, why)."""
    ok, new_shape, why, _ = remove_group_ex(shape, group)
    return ok, new_shape, why


def _stages(rule_names):
    """Face-level rules form one stage (their faces are grouped together); every SET rule is its
    own stage, evaluated in the order listed and only after the earlier stages have nothing left."""
    face = [r for r in rule_names if r not in SET_RULES]
    return ([face] if face else []) + [[r] for r in rule_names if r in SET_RULES]


# A removal that times out wastes the whole time limit. After this many timeouts of one rule the rest of that
# rule's features are skipped (and recorded as failures) instead of trying each of them in turn.
MAX_TIMEOUTS_PER_RULE = int(os.environ.get("CLEANCAD_MAX_TIMEOUTS", "2"))
# Failed removals that return quickly are cheap, but on a big model each one can still take many seconds.
# After this many seconds spent on failed removals of one rule, the rest of that rule is skipped as well.
MAX_WASTED_SECONDS = float(os.environ.get("CLEANCAD_MAX_WASTED_SECONDS", "180"))
# Hard limit for one rule on one model, successes included (on a big model every removal also costs the
# selecting and grouping of what is left).
MAX_SECONDS_PER_RULE = float(os.environ.get("CLEANCAD_MAX_SECONDS_PER_RULE", "300"))


def process(shape, rule_names):
    """Headless end-to-end: repeatedly remove feature groups until none remain.

    Returns (final_shape, removed, failures). Each failure keeps the geometry's
    face signatures so it can be stored for manual correction and fed back into
    Stage 2 retraining (per FR-DEF-04 / NFR-REL-02).
    """
    failed_sigs, removed, failures, batch_dead = set(), [], [], set()
    stages = _stages(rule_names)
    current = shape
    timeouts, wasted, started = {}, {}, {}

    def note_failure(name, why, seconds=0.0):
        if str(why).startswith("timeout"):
            timeouts[name] = timeouts.get(name, 0) + 1
        wasted[name] = wasted.get(name, 0.0) + seconds

    def skip_rest(stage):
        """Once a rule has timed out too often, give up on its remaining features."""
        name = stage[0]
        too_many_timeouts = timeouts.get(name, 0) >= MAX_TIMEOUTS_PER_RULE
        too_slow = wasted.get(name, 0.0) >= MAX_WASTED_SECONDS
        over_budget = time.monotonic() - started.get(name, time.monotonic()) >= MAX_SECONDS_PER_RULE
        if not (too_many_timeouts or too_slow or over_budget):
            return
        rest = select(current, stage, failed_sigs)
        if rest:
            info = info_for(rest)
            info["reason"] = (f"skipped: {timeouts.get(name, 0)} removals of '{name}' timed out already" if too_many_timeouts
                              else f"skipped: failed removals of '{name}' already took {wasted[name]:.0f} s" if too_slow
                              else f"skipped: '{name}' used up its time budget of {MAX_SECONDS_PER_RULE:.0f} s")
            failures.append(info)
            failed_sigs.update(info["sigs"])

    def info_for(group):
        return {"faces": len(group),
                "types": sorted({type(f.Surface).__name__ for f in group}),
                "sigs": [sig(f) for f in group]}

    cache = {}      # stage name -> (shape, groups still to try): while the shape does not change (after a
    #                 failed removal) the next group is taken from here instead of selecting and grouping again

    while True:
        progressed = False
        for stage in stages:
            name = stage[0]
            started.setdefault(name, time.monotonic())
            cached = cache.get(name)
            if cached is not None and cached[0] is current:
                todo = [(g, s) for g, s in cached[1] if not (s & failed_sigs)]
                cache[name] = (current, todo[1:])
                if not todo:
                    continue
                group = todo[0][0]
            else:
                selected = select(current, stage, failed_sigs)
                if not selected:
                    continue
                if name in BATCH and name not in batch_dead:
                    t_batch = time.monotonic()
                    ok, new_shape, why, gone = remove_group_ex(current, selected)
                    if ok:
                        if not any(gone) or (BATCH[name] == "only" and not all(gone)):
                            ok, why = False, "requested faces not (fully) removed"
                    if ok:
                        removed.append(info_for(selected))
                        current, progressed = new_shape, True
                        break
                    note_failure(name, why, time.monotonic() - t_batch)
                    if BATCH[name] == "only":
                        info = info_for(selected)
                        info["reason"] = why
                        failures.append(info)
                        failed_sigs.update(info["sigs"])
                        skip_rest(stage)
                        progressed = True
                        break
                    batch_dead.add(name)   # "try": fall back to per-feature removal below
                    skip_rest(stage)
                    if not select(current, stage, failed_sigs):
                        progressed = True
                        break
                # sig() is not cheap (centre of mass), so the signatures of every group are computed once
                feature_groups = [(g, frozenset(sig(f) for f in g)) for g in groups(current, selected)]
                group = feature_groups[0][0]
                cache[name] = (current, feature_groups[1:])
            t_group = time.monotonic()
            ok, new_shape, why = remove_group(current, group)
            info = info_for(group)
            if ok:
                removed.append(info)
                current = new_shape
                skip_rest(stage)       # only acts when the rule has used up its time budget
            else:
                info["reason"] = why
                failures.append(info)
                failed_sigs.update(info["sigs"])
                note_failure(name, why, time.monotonic() - t_group)
                skip_rest(stage)
            progressed = True
            break
        if not progressed:
            break
    return current, removed, failures


import rules  # noqa: E402,F401  (registers every rule: holes, edges, protrusions, markings)
