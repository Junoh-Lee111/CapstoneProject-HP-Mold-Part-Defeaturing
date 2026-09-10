# Mold-Part Defeaturing

An AI-based automation project for simplifying (defeaturing) mold/part CAD models, developed in partnership with **HP Printing Korea**.

## Project Overview

Before running CAE (Computer-Aided Engineering) simulations, mold/part CAD models contain many small geometric details — holes, fillets, chamfers, ribs, bosses, embosses, etc. — that are necessary for manufacturing but have little impact on simulation accuracy. Removing these details manually ("defeaturing") is time-consuming and inconsistent across engineers.

This project builds an AI system that automatically recognizes these shape features and removes the ones that are unnecessary for analysis, producing a simplified CAD model ready for CAE simulation.

- **Input**: Mold/Part CAD files (.STEP, priority 1; NX, priority 2)
- **Output**: Simplified CAD model suitable for CAE analysis (.STEP)
- **Core task**: Recognize shape features (hole, fillet, chamfer, rib, boss, emboss) and remove unnecessary ones while minimizing the impact on analysis accuracy

### Objectives
- Automate CAE geometry preprocessing
- Learn to judge feature importance and decide what to remove
- Minimize manual intervention

### Required Domain Knowledge
- Shape feature recognition (hole, fillet, chamfer, rib, boss)
- 3D shape classification / ML & deep learning
- Defeaturing rules and training data construction

### Output
- Simulation-ready simplified CAD (.STEP)
- Original vs. defeatured comparison report
- Input format: STEP (priority 1), NX (priority 2)

### Expected Value
- 70–90% reduction in CAD preprocessing time
- Foundation for high-volume simulation automation
- Improved simulation efficiency for HP Printing product development

## Team

| Role | Name |
|---|---|
| Company Partner | HP Printing Korea |
| Mentor | Byoungho Yoo (CAE) |
| Team Lead | Junoh Lee |
| Member | Vangala Hemanth Reddy |
| Member | Tahir Aneela |
| Member | Balcha Kidus Elias |

Detailed role assignment (in progress): [docs/team_rnr.md](docs/team_rnr.md)

## Tech Stack (proposed, pending final confirmation)

| Layer | Choice |
|---|---|
| STEP I/O & geometry manipulation | pythonocc-core |
| B-rep → graph conversion (for ML) | occwl |
| Feature recognition model (candidates) | UV-Net / BRepNet / AAGNet / BrepMFR |
| Simplification quality validation | Gmsh (mesh quality), FreeCAD (visual check) |

See [docs/step_library_comparison.md](docs/step_library_comparison.md) for the full comparison and rationale.

## Repository Structure

```
data/
  raw/          # Original CAD files (.STEP, etc.)
  processed/    # Preprocessed / defeatured CAD files
src/            # Source code
notebooks/      # Experiments / analysis notebooks
models/         # Trained model weights
docs/           # Proposal, requirements, HLD/LLD, reports, etc.
```
