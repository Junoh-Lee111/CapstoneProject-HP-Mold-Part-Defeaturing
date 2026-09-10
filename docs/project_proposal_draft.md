# Project Proposal (Draft) — Mold-Part Defeaturing

> 2026 Capstone Design · Week 2 (9/10) deliverable
> Company Partner: HP Printing Korea | Mentor: Byoungho Yoo (CAE) | Supervising Professor: Edward Youngil Kim

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

- **Input**: Mold/Part CAD files (.STEP priority 1, NX priority 2)
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
- CAD file format (STEP) parsing and manipulation (e.g., OpenCASCADE, python-occ)
- Defining defeaturing rules and building training data

## 6. Expected Value

- 70–90% reduction in CAD preprocessing time
- Foundation for high-volume simulation automation
- Improved simulation efficiency for HP Printing product development

## 7. Team & R&R (draft — pending discussion)

| Name | Role |
|---|---|
| Junoh Lee | TBD |
| Vangala Hemanth Reddy | TBD |
| Tahir Aneela | TBD |
| Balcha Kidus Elias | TBD |

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

- [x] Select STEP processing library → see [docs/step_library_comparison.md](step_library_comparison.md) (pythonocc-core + FreeCAD **confirmed by HP mentor**, 2026-09; occwl proposed)
- [x] NX CAD license constraint → resolved: HP mentor confirmed NX is not required, OCCT-based tooling is sufficient
- [ ] Investigate 3D deep learning approaches for feature recognition (mesh-based vs. B-rep graph-based)
- [ ] Confirm how to obtain sample CAD data from HP
- [ ] Finalize per-member R&R
- [ ] Write team ground rules
