# STEP Processing Library Comparison

> Purpose: research to select libraries for (1) the CAD kernel layer that reads/writes/manipulates STEP files, and
> (2) the layer that converts shape features into a representation (e.g. a graph) AI can recognize, for the Mold-Part Defeaturing project.
> Researched: 2026-09 (subject to change with newer releases; re-check versions before actual adoption)

## 1. Big Picture

```
STEP file (.step)
   │  ① Read/parse (CAD kernel)
   ▼
B-rep model (Face/Edge/Vertex topology)
   │  ② Graph representation conversion (ML wrapper)
   ▼
Face adjacency graph + UV sampling, etc.
   │  ③ Feature recognition model (GNN, etc.)
   ▼
Label: "this face/edge is a hole/fillet/chamfer/rib/boss"
   │  ④ Removal logic (back to the CAD kernel)
   ▼
Simplified STEP file output
```

Steps ①④ are the **CAD kernel library**, ② is the **ML-connecting wrapper**, and ③ is the **feature recognition model** (which we train/implement ourselves).

## 2. CAD Kernel Library Comparison (handles ①④)

All of these are internally based on **Open CASCADE Technology (OCCT)** — an open-source 3D CAD kernel written in C++. So the real question isn't "which kernel" but "how raw vs. how wrapped do we want our access to OCCT to be."

| Library | Nature | STEP Support | Pros | Cons | Recommended Use |
|---|---|---|---|---|---|
| **pythonocc-core** | Near 1:1 Python binding of almost the entire OCCT C++ API (thousands of classes) | Broad data exchange support: IGES/STEP/STL/PLY/OBJ/GLTF, etc. | Most low-level; direct control down to face/edge/vertex level → the fine-grained access required to implement feature recognition/removal logic | API mirrors the C++ style, so there's a learning curve; documentation is sparse | **Core STEP I/O and feature manipulation layer** |
| **build123d** | Latest independent Python CAD framework, derived from CadQuery. Built on OCP (another Python binding of OCCT) | Export/import of major formats including STEP | Pythonic, clean syntax; well-organized shape manipulation API; can also access OCP's low-level types | Optimized for parametric "modeling" (designing new shapes) → may be heavier than needed for our "analyze/decompose an existing model" use case | Auxiliary use for result verification/visualization if needed |
| **CadQuery** | Predecessor of build123d, specialized in parametric CAD scripting | Export to STEP, STL, AMF, 3MF, etc. | Intuitive API, beginner-friendly | More limited low-level (raw OCP type) access compared to build123d | Lower priority (can be replaced by build123d) |
| **FreeCAD Python API** | Python API built into FreeCAD (an open-source CAD program), also OCCT-based | Good STEP read/write, can run alongside the GUI | Results can be checked visually via the GUI (useful for debugging) | Requires the whole heavyweight application; not suited for server/batch automation | Visual verification of results during the prototyping phase |
| **Gmsh** | Dedicated mesh generation library (can interoperate with OCCT geometry) | Mesh generation after STEP import | Needed for evaluating actual CAE mesh quality (validating our project's "success criteria") | Does not support CAD shape editing itself; mesh generation only | Use in the **evaluation stage** (comparing mesh quality/analysis before and after simplification) |

**Conclusion**: the core layer will be **pythonocc-core**. Reasons:
- We need direct access to almost all of OCCT's functionality (face/edge traversal, curvature computation, boolean operations, fillet/chamfer removal APIs, etc.) to implement the core logic of "recognize and remove features"
- build123d/CadQuery are optimized for "designing a new model," so pythonocc-core fits our workflow of "analyzing an existing model and removing only part of it" better
- FreeCAD can be used as an aid for result visualization/verification

## 3. ML-Connecting Wrapper (②)

| Library | Description | Notes |
|---|---|---|
| **occwl** | A lightweight wrapper on top of pythonocc, released by Autodesk AI Lab. Supports B-rep → face adjacency graph conversion and UV parameter domain sampling for faces/edges | Used by the official implementations of several CAD deep learning papers, including UV-Net. **Removes the need to hand-write the repetitive B-rep-to-graph conversion logic** → a strong candidate for adoption in our project |

## 4. Feature Recognition Models (③) — Existing Research/Implementations to Reference

Rather than building from scratch, it's recommended to reference/transfer-learn from the following public implementations:

| Name | Approach | Notes |
|---|---|---|
| **UV-Net** (Autodesk) | Processes each face's UV grid with a CNN and the face adjacency graph with a GNN, then combines them | Pairs well with occwl |
| **BRepNet** (Autodesk) | Defines convolution kernels directly on B-rep coedges (directed edges) → learns directly from B-rep without an intermediate representation | Topology-aware; paper and implementation are public |
| **AAGNet** | Uses an Attributed Adjacency Graph (gAAG) that encodes geometry, topology, and extra attributes together for machining feature recognition | Relatively recent; GitHub includes both training code and a data-generation tool → **top candidate baseline for us** |
| **BrepMFR** | Transformer + graph attention-based machining feature recognition with domain adaptation support | Generalizes well across different CAD sources (useful if HP's real data differs from the training data) |

## 5. Public Datasets for Training/Validation

Until we obtain real HP CAD data, or when data volume is insufficient, we can pretrain/validate with:

| Dataset | Size | Labels | Notes |
|---|---|---|---|
| **MFCAD** | 15,488 models | 16 machining feature types (chamfer, hole, etc.), planar faces only | Relatively simple, good starting point |
| **MFCAD++** | 59,655 models | 24 feature types, includes curved surfaces, 3–10 features per model | More realistic/challenging than MFCAD |
| **Fusion 360 Gallery – Segmentation Dataset** | 35,858 models (STEP format provided) | 8 categories per face (ExtrudeSide/End, CutSide/End, Fillet, Chamfer, RevolveSide/End) | Officially released by Autodesk; includes original STEP files, so it can be used immediately to validate the pythonocc/occwl pipeline |

## 6. Overall Conclusion (proposed initial tech stack)

```
STEP I/O + geometry manipulation   →  pythonocc-core
B-rep → graph conversion           →  occwl
Feature recognition model          →  AAGNet or a custom model based on UV-Net (pretrain on MFCAD/MFCAD++ or Fusion 360 Gallery → fine-tune on HP data)
Before/after validation            →  Gmsh (mesh quality) + FreeCAD (visual check)
```

## 7. Open Questions
- [ ] Verify pythonocc-core's fillet/chamfer auto-removal (defeaturing) APIs actually work as expected (`BRepFilletAPI`, `ShapeUpgrade`, etc.)
- [ ] Confirm occwl is compatible with the latest pythonocc-core version (pin versions after installing)
- [ ] Prototype a pythonocc-core loading pipeline using Fusion 360 Gallery STEP data (W3 goal)
- [ ] Confirm the timeline for obtaining real CAD samples from HP

## References
- [Top Open Source CAD APIs and Libraries for Developers in 2026](https://blog.fileformat.com/cad/top-open-source-cad-api-and-libraries-for-developers-in-2026)
- [build123d GitHub](https://github.com/gumyr/build123d)
- [CadQuery Documentation](https://cadquery.readthedocs.io/en/latest/)
- [pythonocc-core GitHub](https://github.com/tpaviot/pythonocc-core)
- [AAGNet GitHub](https://github.com/whjdark/AAGNet)
- [Fusion 360 Gallery Dataset GitHub](https://github.com/AutodeskAILab/Fusion360GalleryDataset)
- [BRepGAT (JCDE)](https://academic.oup.com/jcde/article/10/6/2384/7453688)
- [FilletRec (arXiv)](https://arxiv.org/pdf/2511.05561)
