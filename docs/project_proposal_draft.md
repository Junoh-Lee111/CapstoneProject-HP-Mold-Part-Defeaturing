# Project Proposal (Draft) — Mold-Part Defeaturing

> 2026 Capstone Design · Week 2 (9/10) deliverable
> Company Partner: HP Printing Korea | Mentor: Byoungho Yoo (CAE) | Supervising Professor: Edward Youngil Kim
>
> **Note:** this is the original Week 2 planning draft. The document actually submitted for the Week 4
> (10/1) proposal presentation is [docs/Project_Proposal.pptx](Project_Proposal.pptx), which reflects
> everything confirmed with the mentor since this draft was written. This file is kept for history and
> has been updated below only to remove factually stale statements (NX priority, R&R "TBD").

## 1. Project Overview

**Title**: AI-based Mold/Part CAD Shape Simplification (Mold-Part Defeaturing) Automation

Before running CAE (Computer-Aided Engineering) analysis, real product CAD designs contain many small shape details (holes, fillets, chamfers, ribs, bosses, embosses, etc.) that have little impact on structural/flow analysis results. These details significantly increase mesh generation and analysis time while contributing little to analysis accuracy. This project develops automation technology that has AI automatically recognize and remove such unnecessary shapes, producing a simplified CAD model ready for CAE analysis.

## 2. Background & Problem Statement (Why)

- CAE engineers spend significant time manually removing unnecessary shapes from CAD models before analysis ("defeaturing")
- Manual defeaturing depends on engineer experience, is inconsistent, and doesn't scale to large volumes of parts
- CAD preprocessing is a bottleneck in HP Printing's high-volume simulation / product development process

## 3. Objectives

1. Automate CAE geometry preprocessing
2. Learn to judge the importance of shape features (hole, fillet, chamfer, rib, boss, emboss) and decide which to remove
3. Minimize manual intervention

## 4. Scope (MVP)

- **Input**: Mold/Part CAD files (.STEP only — NX is not required, confirmed by HP mentor)
- **Output**:
  - Simulation-ready simplified CAD model (.STEP)
  - Original vs. simplified shape comparison report
- The top priority is accuracy and minimizing impact on analysis results; accuracy on core features (hole/fillet/chamfer/rib/boss) takes precedence over broadening the range of supported shape types.

### Stretch Goals (post-MVP, needs discussion)
- Expand support to additional feature types such as emboss
- Direct NX format support
- Automated validation loop based on analysis results (stress/deformation, etc.)

## 5. Required Domain Knowledge

- Shape feature recognition (hole, fillet, chamfer, rib, boss)
- 3D shape classification / ML & deep learning (e.g., point cloud, mesh, B-rep-based models)
- CAD file format (STEP) parsing and manipulation (FreeCAD Python API, headless — confirmed toolchain)
- Defining defeaturing rules and building training data

## 6. Expected Value

- 70–90% reduction in CAD preprocessing time
- Foundation for high-volume simulation automation
- Improved simulation efficiency for HP Printing product development

## 7. Team & R&R

Finalized — see [docs/team_rnr.md](team_rnr.md) for the current sub-role breakdown.

| Name | Sub-Role |
|---|---|
| Junoh Lee | Team Lead / CAD Geometry Engineer |
| Hemanth Reddy Vangala | ML / Graph Model Engineer |
| Aneela Tahir | Data Pipeline & Test-Data Engineer |
| Balcha Kidus Elias | Integration & Test Engineer |

## 8. Timeline

- W3: system architecture diagram, FR/NFR
- W4: proposal presentation, start HLD
- W6: submit HLD
- W7: submit LLD
- W8: progress presentation to company mentor
- W9–W11: implementation (prototype → integration/testing)
- W13: performance/accuracy analysis
- W15: final presentation & demo

## 9. Open Items / Next Actions

- [x] Select STEP processing library → see [docs/step_library_comparison.md](step_library_comparison.md) §9 (**FreeCAD Python API confirmed by HP mentor**, 2026-09-18; cadquery optional for STEP generation only)
- [x] NX CAD license constraint → resolved: HP mentor confirmed NX is not required
- [x] Confirm how to obtain sample CAD data from HP → resolved: HP's real CAD data is confidential and will not be provided; the team authors simple CAD shapes itself, supplemented by public datasets
- [x] Finalize per-member R&R → see [docs/team_rnr.md](team_rnr.md)
- [x] Write team ground rules → see [docs/Team2_Ground_Rules.docx](Team2_Ground_Rules.docx)
- [x] Core mechanism prototype → `src/cleancad_core.py`, verified against 9 self-authored example shapes (9/9 pass, `src/run_headless.py`)
- [ ] Investigate 3D deep learning approaches for feature recognition (mesh-based vs. B-rep graph-based); pick the specific model (UV-Net/BRepNet/AAGNet/BrepMFR)
