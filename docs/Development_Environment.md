# Development Environment

> Verified against the team lead's machine on 2026-09-30. Other team members: see "Per-OS notes" below and
> update this file with your own confirmed paths once you've set up — don't assume the macOS paths apply.

## 1. Overview

CleanCAD's code has two separate runtime contexts, because the confirmed CAD toolchain
(FreeCAD Python API, see [step_library_comparison.md](step_library_comparison.md) §9) is not a pip package —
it's the Python interpreter *embedded inside FreeCAD itself*.

| Context | Interpreter | Used by | External pip deps |
|---|---|---|---|
| CAD pipeline (M1, M5, current prototype) | FreeCAD's own embedded Python | `src/engine/cleancad_core.py`, `gen_examples.py`, `run_headless.py`, `demo_freecad.py` | **None** — only `Part`, `FreeCAD`, `FreeCADGui`, `ImportGui`, `PySide` (all built into FreeCAD) + stdlib |
| ML / graph / docs tooling | System Python 3 | future `M2`–`M4` (graph conversion, GNN), and one-off doc/report generation scripts | project-specific (see §5) |

This split matters: running `src/*.py` with your system `python3` will fail (`ModuleNotFoundError: No module
named 'Part'`) — they must be run through FreeCAD's own interpreter (§3).

## 2. Confirmed Toolchain Facts

- **CAD engine**: FreeCAD, **headless/standalone** execution — no NX license needed (HP mentor confirmed
  2026-09-18)
- **cadquery**: optional, STEP-generation only — not the primary toolchain
- **occwl**: not usable as-is (built on `pythonocc-core`, which we are not using) — graph conversion (M2) will
  be built directly on the FreeCAD API instead (see [team_rnr.md](team_rnr.md))

## 3. macOS Setup (verified on team lead's machine)

| Item | Value |
|---|---|
| OS | macOS 26.6.2, Apple Silicon (arm64) |
| FreeCAD | **1.1.3** (Revision 20260725), installed as `/Applications/FreeCAD.app` |
| Headless binary | `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd` |
| GUI binary | `/Applications/FreeCAD.app/Contents/MacOS/FreeCAD` |
| System Python (for non-CAD tooling only) | 3.11.9 |

**Gotcha found while writing this doc**: `INDEX.md` in the workspace folder (and earlier notes) refer to
running scripts via a bare `FreeCADCmd` command. On this machine that command is **not on `PATH`** — the real
binary is the lowercase `freecadcmd` shown above, one level deeper than expected
(`Contents/Resources/bin/`, not `Contents/MacOS/`). Use the full path, or add an alias:

```bash
alias FreeCADCmd="/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
```

### Running the pipeline (headless)

```bash
cd CapstoneProject-HP-Mold-Part-Defeaturing
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd src/validation/gen_examples.py
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd src/validation/run_headless.py
```

Output (STEP files, `manifest.json`, `logs/report.md`) is written to `$CLEANCAD_WORKDIR` (default
`~/Documents/CleanCAD_Workspace`), never into the repo — see §4.

### Running the live GUI demo

```bash
src/demo/fcdemo.sh --quit          # all example shapes
src/demo/fcdemo.sh near_edge,ribbed  # only these examples
```

`fcdemo.sh` launches the full FreeCAD GUI app (`FREECAD_APP`, default `/Applications/FreeCAD.app`) and drives
it via `demo_freecad.py`; screenshots land in `$CLEANCAD_WORKDIR/snapshots/`.

**Entry-point quirk**: FreeCADCmd/FreeCAD set a script's `__name__` to the file's stem, not `"__main__"`, so
`gen_examples.py`/`run_headless.py` call `main()` unconditionally instead of using a
`if __name__ == "__main__":` guard. Keep this in mind if you add new entry-point scripts.

## 4. Environment Variables

All generated output (STEP files, screenshots, logs) is kept **out of the git repo** in a single workspace
folder, controlled by:

| Variable | Default | Purpose |
|---|---|---|
| `CLEANCAD_WORKDIR` | `~/Documents/CleanCAD_Workspace` | root for all generated samples/snapshots/logs |
| `CLEANCAD_DELAY_MS` | `1200` | delay (ms) between animation steps in the live demo |
| `CLEANCAD_AUTOQUIT` | unset | set to `1` to auto-close FreeCAD after the demo (`fcdemo.sh --quit`) |
| `FREECAD_APP` | `/Applications/FreeCAD.app` | path to the FreeCAD app bundle, for `fcdemo.sh` |

Code lives in the repo (`src/`); nothing under `$CLEANCAD_WORKDIR` is ever committed.

## 5. System Python (docs/tooling only — not the CAD pipeline)

Used only for one-off scripts that generate/patch the `.docx`/`.pptx` deliverables in `docs/` (not part of
the CleanCAD pipeline itself). Confirmed on the team lead's machine:

- Python 3.11.9
- `python-pptx` 1.0.2
- `python-docx` 1.2.0

No `requirements.txt` / `pyproject.toml` exists yet for this — **open item**, not created here since none of
the actual M1–M8 pipeline code needs it yet. When M2–M4 (graph conversion, GNN) start, that's where a real
dependency file (likely `torch`, a graph library, etc., CPU-only per NFR-PERF-01) should be introduced —
owned by whoever starts that work (Hemanth, per [team_rnr.md](team_rnr.md)).

## 6. Per-OS Notes (unverified — please confirm and edit this section)

The macOS paths and `fcdemo.sh`'s `FREECAD_APP` default only apply to macOS. Team members on Windows/Linux:

- **Windows**: FreeCAD typically installs to `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe` (path may
  differ by installer/version — confirm on your machine and update this file).
- **Linux**: usually just `freecadcmd` on `PATH` after installing the `freecad` package, or an AppImage —
  again, confirm your actual path and add it here rather than assuming the macOS layout.
- `fcdemo.sh` currently assumes a macOS `.app` bundle structure; it is not yet adapted for Windows/Linux
  launch commands. If you need the live GUI demo on another OS, flag it — the script's `FREECAD_APP`
  override exists for exactly this, but the launch line itself (`Contents/MacOS/FreeCAD`) is mac-specific.

## 7. Repository Layout

```
CapstoneProject-HP-Mold-Part-Defeaturing/
├── src/                  code (in git)
│   ├── cleancad_core.py    mechanism: groups() / remove_group() / process() + @rule test scaffolding
│   ├── gen_examples.py     builds 9 example shapes + manifest.json
│   ├── run_headless.py     headless end-to-end check vs. manifest.json
│   ├── demo_freecad.py     live FreeCAD GUI demo
│   └── fcdemo.sh           launcher for the live demo
├── docs/                 FRD, NFRD, HLD, R&R, proposal, this file, etc. (in git)
├── data/, models/, notebooks/  (scaffolded, not yet populated)
└── (generated output — STEP files, screenshots, logs — lives OUTSIDE this repo, see §4)
```

## Related Documents
- [step_library_comparison.md](step_library_comparison.md) — toolchain decision rationale
- [architecture.md](architecture.md) — pipeline architecture (M1–M8)
- [team_rnr.md](team_rnr.md) — who owns which module
