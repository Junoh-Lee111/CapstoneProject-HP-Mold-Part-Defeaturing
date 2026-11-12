# Face-level rule evaluation

Truth = faces of the generated shape that are not part of the clean base shape. Generated cases only (9); logos are out of scope.

## scaffolding rules (cyl/prot/recess/chamfer)

| case | truth | selected | TP | FP | FN | precision | recall | missed types |
|---|---|---|---|---|---|---|---|---|
| plate_hole_fillets | 5 | 5 | 5 | 0 | 0 | 1.00 | 1.00 | - |
| curved_press | 6 | 6 | 6 | 0 | 0 | 1.00 | 1.00 | - |
| ribbed | 17 | 17 | 17 | 0 | 0 | 1.00 | 1.00 | - |
| chamfer | 5 | 5 | 5 | 0 | 0 | 1.00 | 1.00 | - |
| boss | 3 | 2 | 2 | 0 | 1 | 1.00 | 0.67 | boss |
| emboss | 25 | 25 | 25 | 0 | 0 | 1.00 | 1.00 | - |
| rib_network | 33 | 33 | 33 | 0 | 0 | 1.00 | 1.00 | - |
| near_edge | 8 | 8 | 8 | 0 | 0 | 1.00 | 1.00 | - |
| fail_demo | 0 | 1 | 0 | 1 | 0 | 0.00 | n/a | - |
| pocket | 0 | 0 | 0 | 0 | 0 | n/a | n/a | - |
| large_features | 0 | 0 | 0 | 0 | 0 | n/a | n/a | - |

Overall: precision 0.99, recall 0.99 (TP 101, FP 1, FN 1).

| feature type | truth faces | found | recall |
|---|---|---|---|
| boss | 3 | 2 | 0.67 |
| chamfer | 4 | 4 | 1.00 |
| countersink | 1 | 1 | 1.00 |
| emboss | 25 | 25 | 1.00 |
| fillet | 11 | 11 | 1.00 |
| hole | 4 | 4 | 1.00 |
| notch | 1 | 1 | 1.00 |
| rib | 53 | 53 | 1.00 |

## ref rules, recognition only (size limits 50 mm)

| case | truth | selected | TP | FP | FN | precision | recall | missed types |
|---|---|---|---|---|---|---|---|---|
| plate_hole_fillets | 5 | 5 | 5 | 0 | 0 | 1.00 | 1.00 | - |
| curved_press | 6 | 6 | 6 | 0 | 0 | 1.00 | 1.00 | - |
| ribbed | 17 | 2 | 2 | 0 | 15 | 1.00 | 0.12 | rib |
| chamfer | 5 | 1 | 0 | 1 | 5 | 0.00 | 0.00 | chamfer, countersink |
| boss | 3 | 1 | 1 | 0 | 2 | 1.00 | 0.33 | boss |
| emboss | 25 | 0 | 0 | 0 | 25 | n/a | 0.00 | emboss |
| rib_network | 33 | 0 | 0 | 0 | 33 | n/a | 0.00 | rib |
| near_edge | 8 | 2 | 2 | 0 | 6 | 1.00 | 0.25 | notch, rib |
| fail_demo | 0 | 1 | 0 | 1 | 0 | 0.00 | n/a | - |
| pocket | 0 | 0 | 0 | 0 | 0 | n/a | n/a | - |
| large_features | 0 | 0 | 0 | 0 | 0 | n/a | n/a | - |

Overall: precision 0.89, recall 0.16 (TP 16, FP 2, FN 86).

| feature type | truth faces | found | recall |
|---|---|---|---|
| boss | 3 | 1 | 0.33 |
| chamfer | 4 | 0 | 0.00 |
| countersink | 1 | 0 | 0.00 |
| emboss | 25 | 0 | 0.00 |
| fillet | 11 | 11 | 1.00 |
| hole | 4 | 4 | 1.00 |
| notch | 1 | 0 | 0.00 |
| rib | 53 | 0 | 0.00 |

## ref rules, hp_example (holes < 6 mm, fillets < 10 mm)

| case | truth | selected | TP | FP | FN | precision | recall | missed types |
|---|---|---|---|---|---|---|---|---|
| plate_hole_fillets | 5 | 4 | 4 | 0 | 1 | 1.00 | 0.80 | hole |
| curved_press | 6 | 6 | 6 | 0 | 0 | 1.00 | 1.00 | - |
| ribbed | 17 | 2 | 2 | 0 | 15 | 1.00 | 0.12 | rib |
| chamfer | 5 | 0 | 0 | 0 | 5 | n/a | 0.00 | chamfer, countersink |
| boss | 3 | 1 | 1 | 0 | 2 | 1.00 | 0.33 | boss |
| emboss | 25 | 0 | 0 | 0 | 25 | n/a | 0.00 | emboss |
| rib_network | 33 | 0 | 0 | 0 | 33 | n/a | 0.00 | rib |
| near_edge | 8 | 2 | 2 | 0 | 6 | 1.00 | 0.25 | notch, rib |
| fail_demo | 0 | 0 | 0 | 0 | 0 | n/a | n/a | - |
| pocket | 0 | 0 | 0 | 0 | 0 | n/a | n/a | - |
| large_features | 0 | 0 | 0 | 0 | 0 | n/a | n/a | - |

Overall: precision 1.00, recall 0.15 (TP 15, FP 0, FN 87).

| feature type | truth faces | found | recall |
|---|---|---|---|
| boss | 3 | 1 | 0.33 |
| chamfer | 4 | 0 | 0.00 |
| countersink | 1 | 0 | 0.00 |
| emboss | 25 | 0 | 0.00 |
| fillet | 11 | 11 | 1.00 |
| hole | 4 | 3 | 0.75 |
| notch | 1 | 0 | 0.00 |
| rib | 53 | 0 | 0.00 |

