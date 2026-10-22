"""Worker process for cleancad_core: runs FreeCAD's defeaturing() on request, so that the caller can
give up (and kill this process) when the CAD kernel hangs.

Started by cleancad_core as `freecadcmd src/defeature_worker.py` with CLEANCAD_WORKER_DIR set.
Protocol (files in that directory, written atomically by rename):
  req<N>.brep + req<N>.json {"faces": [indices into shape.Faces], "delay": seconds (tests only),
                              "op": "cut" (optional; then req<N>.tool.brep is cut away instead)}
  -> res<N>.brep + res<N>.json {"faces", "volume", "valid", "gone": [...]} or {"error": "..."}
Exits when the parent process is gone or a file named "stop" appears.
"""
import json
import os
import time

import Part

WORKDIR = os.environ["CLEANCAD_WORKER_DIR"]
PARENT = int(os.environ["CLEANCAD_PARENT_PID"])


def path(name):
    return os.path.join(WORKDIR, name)


def write_atomic(name, text):
    with open(path(name + ".tmp"), "w") as fh:
        fh.write(text)
    os.rename(path(name + ".tmp"), path(name))


def parent_alive():
    try:
        os.kill(PARENT, 0)
        return True
    except OSError:
        return False


def handle(n):
    try:
        meta = json.load(open(path(f"req{n}.json")))
        if meta.get("delay"):
            time.sleep(meta["delay"])
        shape = Part.Shape()
        shape.importBrepFromString(open(path(f"req{n}.brep")).read())
        all_faces = list(shape.Faces)
        group = [all_faces[i] for i in meta["faces"]]
        if meta.get("op") == "cut":        # remove a protrusion by cutting away a prism instead
            tool = Part.Shape()
            tool.importBrepFromString(open(path(f"req{n}.tool.brep")).read())
            new_shape = shape.cut(tool)
        else:
            new_shape = shape.defeaturing(group)
        after = list(new_shape.Faces)
        write_atomic(f"res{n}.brep", new_shape.exportBrepToString())
        res = {"faces": len(after), "volume": new_shape.Volume, "valid": new_shape.isValid(),
               "gone": [not any(f.isSame(a) for a in after) for f in group]}
    except BaseException as e:      # noqa: BLE001 - always answer, the caller is waiting
        res = {"error": repr(e)}
    write_atomic(f"res{n}.json", json.dumps(res))


def main():
    write_atomic("ready", "1")
    done = set()
    while parent_alive() and not os.path.exists(path("stop")):
        pending = sorted(int(f[3:-5]) for f in os.listdir(WORKDIR)
                         if f.startswith("req") and f.endswith(".json") and int(f[3:-5]) not in done)
        if not pending:
            time.sleep(0.01)
            continue
        done.add(pending[0])
        handle(pending[0])


# FreeCADCmd runs this file with __name__ set to the module name, so call main() unconditionally.
main()
