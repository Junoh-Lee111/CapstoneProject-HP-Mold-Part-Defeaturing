"""Checks of the defeaturing timeout guard (headless).

Run: FreeCADCmd src/validation/test_timeout.py
 1. a removal through the worker process works and equals the in-process result;
 2. a removal that never answers is cut off at the limit and reported as a timeout, and the next
    removal works again (the worker is restarted);
 3. process() records the timed-out feature as a failure and still finishes the rest.
Optional real-data check: CLEANCAD_HANG_FILE=<step file that makes defeaturing hang> (not in the repo).
"""
import os
import sys
import time

import Part

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):                       # layers: engine/, rules/, ...
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core

V = core.FreeCAD.Vector
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} {detail}")


def plate_with_holes(*xs):
    shape = Part.makeBox(100, 60, 3)
    for x in xs:
        shape = shape.cut(Part.makeCylinder(4, 10, V(x, 30, -2)))
    return shape


# 1. normal removal
plate = plate_with_holes(50)
hole = [f for f in plate.Faces if type(f.Surface).__name__ == "Cylinder"]
t = time.time()
ok1, s1, why1, gone1 = core.remove_group_ex(plate, hole, timeout=30)       # includes worker start-up
ok0, s0, why0, gone0 = core.remove_group_ex(plate, hole, timeout=0)        # in-process reference
check("removal through the worker", ok1 and all(gone1) and len(s1.Faces) == len(plate.Faces) - 1,
      f"({why1}, {time.time() - t:.1f}s incl. start-up)")
check("worker == in-process", ok0 and len(s0.Faces) == len(s1.Faces) and abs(s0.Volume - s1.Volume) < 1e-6)

# 2. a call that never answers
t = time.time()
okh, sh, whyh, _ = core.remove_group_ex(plate, hole, timeout=3, _test_delay=60)
check("hang is cut off", not okh and whyh.startswith("timeout") and sh is plate and time.time() - t < 10,
      f"({whyh}, {time.time() - t:.1f}s)")
ok2, s2, why2, _ = core.remove_group_ex(plate, hole, timeout=30)
check("next removal works again", ok2 and len(s2.Faces) == len(plate.Faces) - 1, why2)

# 3. process() survives it: the first removal hangs, the second one is fine
orig_run, calls = core._WORKER.run, {"n": 0}


def first_call_hangs(shape, group, timeout, delay=0, tool=None):
    calls["n"] += 1
    return orig_run(shape, group, timeout, 60 if calls["n"] == 1 else delay, tool)


core._WORKER.run = first_call_hangs
core.DEFEATURE_TIMEOUT = 3
t = time.time()
final, removed, failures = core.process(plate_with_holes(30, 70), ["cyl"])
core._WORKER.run = orig_run
check("process continues after a timeout",
      len(failures) == 1 and "timeout" in failures[0]["reason"] and len(removed) == 1 and time.time() - t < 30,
      f"(removed {len(removed)}, failures {[f['reason'] for f in failures]}, {time.time() - t:.0f}s)")

# 4. repeated timeouts of one rule stop that rule instead of trying every feature
real_run = core._WORKER.run
core._WORKER.run = lambda shape, group, timeout, delay=0, tool=None: ("timeout", "no answer after stub")
core.MAX_TIMEOUTS_PER_RULE = 2
t = time.time()
final, removed, failures = core.process(plate_with_holes(20, 50, 80), ["cyl"])
core._WORKER.run = real_run
reasons = [f["reason"] for f in failures]
check("repeated timeouts skip the rest of the rule",
      len(removed) == 0 and len(failures) == 3 and reasons[-1].startswith("skipped") and time.time() - t < 10,
      f"({reasons})")

# 5. failed removals that are slow but not timeouts also stop the rule after a time budget
real_remove = core.remove_group
core.remove_group = lambda shape, group: (time.sleep(0.6), (False, shape, "no-op (shape unchanged)"))[1]
core.MAX_WASTED_SECONDS = 1.0
final, removed, failures = core.process(plate_with_holes(20, 50, 80), ["cyl"])
core.remove_group = real_remove
reasons = [f["reason"] for f in failures]
check("slow failures use up a time budget", len(failures) == 3 and reasons[-1].startswith("skipped: failed removals"),
      f"({reasons})")

# optional: the real thing
real = os.environ.get("CLEANCAD_HANG_FILE")
if real:
    core.DEFEATURE_TIMEOUT = float(os.environ.get("CLEANCAD_DEFEATURE_TIMEOUT", "20"))
    shape = Part.read(real)
    t = time.time()
    final, removed, failures = core.process(shape, ["ref_fillets"])
    print(f"RESULT INFO real file: removed {len(removed)}, failures {[f['reason'] for f in failures]}, "
          f"{time.time() - t:.0f}s")

print(f"SUMMARY {sum(results)}/{len(results)} PASS")
