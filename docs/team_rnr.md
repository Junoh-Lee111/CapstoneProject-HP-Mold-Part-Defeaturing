# Team R&R (Role & Responsibility)

- Project Name: Mold-Part Defeaturing
- Team Name: HP2
- Company Partner / Mentor: HP Printing Korea / Byoungho Yoo (CAE)

> **Status: revised per professor's R&R Review feedback** (No Sub-Role / Need Coding Role). Sub-roles now split out under Technical Role & Responsibility, each with an explicit coding deliverable, plus a separate Non-technical Role & Responsibility section.

## Team Leader

| Item | Value |
|---|---|
| Team Leader | Junoh Lee |

## Technical Role & Responsibility

Sub-roles follow the project pipeline (see [docs/step_library_comparison.md](step_library_comparison.md): STEP input → B-rep graph conversion → feature recognition model → validation). Every sub-role has an explicit code deliverable.

| Sub-Role | Responsibility | Assignee |
|---|---|---|
| CAD Geometry Engineer | Write the CAD I/O and geometry manipulation code: STEP parsing, feature extraction/removal, geometry healing (FreeCAD Python API, headless; cadquery optional for STEP generation). Mechanism prototyped in `src/cleancad_core.py`, verified against 9 example shapes (9/9 pass, see `src/run_headless.py`) | Junoh Lee |
| ML / Graph Model Engineer | Write the B-rep -> graph conversion code (in-house via FreeCAD API — occwl needs re-evaluation, since it is built on pythonocc-core) and train the GNN-based feature recognition model | Hemanth Reddy Vangala |
| Data Pipeline & Test-Data Engineer | Write scripts to programmatically generate test CAD shapes and to automate before/after comparison & mesh-quality evaluation (Gmsh) | Aneela Tahir |
| Integration & Test Engineer | Write the glue code connecting each module's input/output, plus unit/integration test code for the pipeline | Balcha Kidus Elias |

## Non-technical Role & Responsibility

| Role | Assignee |
|---|---|
| Co-Leader | Hemanth Reddy Vangala |
| Meeting Notes | Balcha Kidus Elias |
| Report Writer | Junoh Lee |
| Presentation Maker | Aneela Tahir |

## Collaboration Principles

1. Share progress in a weekly team meeting during class time (use the Weekly Report template)
2. Track task requests and progress via KakaoTalk / GitHub issues
3. Track individual contribution based on GitHub commit history and meeting notes
4. Work on a personal feature branch (e.g. `feature/<name>-<topic>`) and open a Pull Request rather than pushing directly to `master`; the team lead reviews and merges. (Convention only for now — not yet enforced by GitHub branch protection.)

## Related Documents
- [Project Proposal Draft](project_proposal_draft.md)
- [STEP Library Comparison](step_library_comparison.md)
- [README](../README.md)
