"""Remove a chosen set of faces from a shape in one go, for the screen's live preview.

The rules decide WHICH faces; this only applies a selection: the connected groups of the selected faces are removed one
after another with cleancad_core.remove_group (so every safety of the engine applies), a group that cannot be removed
is kept and recorded. The original shape is never changed."""
import os
import sys
import time

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402


class Result:
    """shape: the result; removed: number of groups removed; failures: list of dicts (faces, types, sigs, reason);
    failed: signatures of the faces that could not be removed; seconds; stopped: True if the time budget ran out."""

    def __init__(self, shape):
        self.shape, self.removed, self.failures, self.failed = shape, 0, [], set()
        self.seconds, self.stopped = 0.0, False


def remove_selected(shape, selected, budget=None):
    """selected: set of face signatures (cleancad_core.sig) of `shape`. budget: seconds after which the rest is skipped."""
    t0 = time.monotonic()
    res = Result(shape)
    selected = set(selected)
    while True:
        faces = [f for f in res.shape.Faces if core.sig(f) in selected and core.sig(f) not in res.failed]
        groups = core.groups(res.shape, faces) if faces else []
        if not groups:
            break
        if budget is not None and time.monotonic() - t0 > budget:
            res.stopped = True
            break
        group = groups[0]
        ok, new_shape, why = core.remove_group(res.shape, group)
        if ok:
            res.shape = new_shape
            res.removed += 1
        else:
            res.failed.update(core.sig(f) for f in group)
            res.failures.append({"faces": len(group), "types": sorted({type(f.Surface).__name__ for f in group}),
                                 "sigs": [core.sig(f) for f in group], "reason": why})
    res.seconds = time.monotonic() - t0
    return res
