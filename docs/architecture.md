# System Architecture (W3)

> **Status: CAD kernel layer confirmed** (pythonocc-core/OCCT + FreeCAD — validated by HP mentor Byoungho Yoo, 2026-09, see [step_library_comparison.md](step_library_comparison.md) §8). **Feature Recognition Model and Decision Logic still open**, pending team discussion.

## 1. Overall Pipeline

```mermaid
flowchart LR
    subgraph INPUT["Input"]
        A[Mold/Part CAD\n.STEP file]
    end

    subgraph CORE["Core Processing Pipeline"]
        B["CAD Kernel Layer\n(pythonocc-core)\nSTEP parsing, B-rep access"]
        C["Graph Conversion Layer\n(occwl)\nface adjacency graph + UV sampling"]
        D["Feature Recognition Model\n(GNN, e.g. AAGNet / UV-Net)\nclassify each face/feature"]
        E["Decision Logic\nkeep vs. remove per feature\n(rule + model confidence)"]
        F["Feature Removal Engine\n(pythonocc-core)\nsuppress fillet/chamfer/hole/rib/boss"]
    end

    subgraph OUTPUT["Output"]
        G[Simplified CAD\n.STEP file]
        H[Comparison Report\noriginal vs. defeatured]
    end

    subgraph EVAL["Validation"]
        I["Mesh Quality Check\n(Gmsh)"]
        J["Visual Check\n(FreeCAD)"]
    end

    A --> B --> C --> D --> E --> F --> G
    F --> H
    G --> I
    G --> J
    I --> H
```

## 2. Offline: Model Training Pipeline

The Feature Recognition Model is trained and deployed ahead of time, separately from the pipeline above.

```mermaid
flowchart LR
    subgraph DATA["Training Data"]
        K1["Public datasets\nMFCAD / MFCAD++ /\nFusion 360 Gallery"]
        K2["Self-authored simple CAD shapes\n(HP cannot share real CAD data\n- confidential)"]
    end
    L["Graph Conversion\n(occwl)"]
    M["Model Training\n(GNN: AAGNet / UV-Net, etc.)"]
    N["Trained Model Weights"]

    K1 --> L
    K2 --> L
    L --> M --> N
    N -.deployed to.-> D2["Feature Recognition Model\n(D in the Core Pipeline)"]
```

## 3. Layer Descriptions

| Layer | Component | Responsibility |
|---|---|---|
| Input | STEP file | Original CAD provided by the user/HP |
| CAD Kernel | pythonocc-core | Parse STEP, access face/edge/vertex, execute the final shape manipulation (feature removal) |
| Graph Conversion | occwl | Convert B-rep into a face adjacency graph + UV parameter samples (model input format) |
| Feature Recognition Model | GNN-family model (candidates: UV-Net/BRepNet/AAGNet/BrepMFR) | Classify each face/feature as hole/fillet/chamfer/rib/boss, etc., and whether it has a large or small impact on analysis |
| Decision Logic | Rules + model confidence combined | Final judgment on whether a feature can be removed, based on model output (start rule-based, evolve toward learning-based) |
| Feature Removal Engine | pythonocc-core (BRepFilletAPI, ShapeUpgrade, etc.) | Actually suppress/remove features judged removable |
| Output | Simplified STEP + comparison report | Final deliverable |
| Validation | Gmsh (mesh quality), FreeCAD (visual) | Compare before/after simplification, verify success criteria (70–90% preprocessing time reduction) |

## 4. Confirmed Decisions

- [x] **CAD kernel: pythonocc-core (OCCT) for STEP I/O and feature manipulation.** Confirmed 2026-09 — HP mentor Byoungho Yoo reviewed the NX license constraint and independently validated that OCCT can replace NX for geometry creation and defeaturing, with a working preliminary test.
- [x] **Visual verification: FreeCAD.** Confirmed alongside the above — same role as originally proposed.
- [x] **NX support is not required.** The project can proceed entirely without NX CAD access.
- [x] **Training/test data will not come from HP.** HP's real CAD data is confidential and cannot be shared. Instead, the team will author simple CAD shapes themselves (plus public datasets like MFCAD/MFCAD++/Fusion 360 Gallery) for training and validation.

## 5. Open Points (needs team discussion/approval)

- [ ] Decide the final Feature Recognition Model among the candidates (UV-Net vs. BRepNet vs. AAGNet vs. BrepMFR) — see the detailed comparison in [step_library_comparison.md](step_library_comparison.md). HP mentor also flagged this as the next challenge: selecting which features to defeature, likely via AI-based training.
- [ ] Whether to start the Decision Logic as rule-based or go learning-based from the start — related to the teammate question "what happens when the model is uncertain about removing a feature — fall back to manual human review?"
- [ ] Comparison report format: simple text summary (e.g. "removed 5 fillets, 6 holes, 5 ribs") vs. visual before/after reference, or both — raised by a teammate
- [ ] Whether a web demo/UI is needed and in what form (currently assuming a batch/CLI pipeline only)

## Related Documents
- [STEP Library Comparison](step_library_comparison.md)
- [Team R&R](team_rnr.md)
- [Project Proposal Draft](project_proposal_draft.md)
