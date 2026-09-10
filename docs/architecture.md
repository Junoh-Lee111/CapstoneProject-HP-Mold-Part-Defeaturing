# System Architecture (Draft — W3)

> **Status: draft, pending approval.** The architecture below is drawn from the recommended tech stack researched in [step_library_comparison.md](step_library_comparison.md), and will be finalized after the team lead's approval.

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
        K2["HP sample CAD\n(secured over time)"]
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

## 4. Open Points (needs team discussion/approval)

- [ ] Decide the final Feature Recognition Model among the candidates (UV-Net vs. BRepNet vs. AAGNet vs. BrepMFR) — see the detailed comparison in the "tech stack rationale" discussion
- [ ] Whether to start the Decision Logic as rule-based or go learning-based from the start
- [ ] Whether a web demo/UI is needed and in what form (currently assuming a batch/CLI pipeline only)
- [ ] Adjust the training pipeline schedule depending on when HP's real data becomes available

## Related Documents
- [STEP Library Comparison](step_library_comparison.md)
- [Team R&R](team_rnr.md)
- [Project Proposal Draft](project_proposal_draft.md)
