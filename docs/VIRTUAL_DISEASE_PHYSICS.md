# Virtual Disease causal physics

## PR 3 status

This document describes implementation stage 3 of 5 for the first-party VascuQuest Virtual Disease subsystem.

PR 3 adds **causal disease transformations and disease-aware solver coupling only**. It does not create a runtime disease dataset, generate a virtual-disease population through the public API, materialise disease-qualified vectors, expose a disease-generation CLI, or make a clinical-validation claim.

The healthy parent `BaselineCardiovascularState` introduced in PR 2 remains immutable. A disease request produces a separate `DiseasePhysicsModel` containing:

- the unchanged healthy parent state;
- the frozen `DiseaseSpecification`;
- a transformed solver network;
- any explicit local excess pressure-loss terms;
- the exact set of modified PWDB segment IDs;
- modelling assumptions and citations.

This is the causal layer that later runtime-dataset work will execute and materialise.

## Frozen anatomy

Disease targets are defined from the public PWDB 116-artery input network, not inferred from the 13 common waveform measurement sites.

The frozen focal targets are:

| Disease target | PWDB segment |
|---|---:|
| Right common carotid | 5 |
| Right internal carotid | 12 |
| Left common carotid | 15 |
| Left internal carotid | 16 |
| Left common iliac | 42 |
| Right common iliac | 43 |
| Left external iliac | 44 |
| Right external iliac | 50 |

The fusiform abdominal-aortic path is:

```text
28 -> 35 -> 37 -> 39 -> 41
```

corresponding to the five main abdominal-aortic segments in the source 116-artery model.

This distinction is intentional. A source measurement-site convention must not be repurposed as anatomical disease truth.

## Focal carotid and iliac stenosis

A requested diameter stenosis is imposed on the selected source artery as a smooth raised-cosine lumen reduction. The profile is continuous with the healthy radius at both lesion boundaries and reaches the requested relative diameter reduction at the lesion centre in the continuous model.

The lesion must fit entirely inside the selected PWDB segment. Executable v1 accepts

```text
0 <= diameter stenosis < 1
```

because complete geometric occlusion would create zero area and lies outside the open-vessel 1-D solver domain. A requested stenosis of zero is an exact causal no-op.

### Excess stenosis pressure loss

Changing the 1-D lumen alone does not recover all pressure loss caused by a focal stenosis, particularly the energy loss associated with downstream flow separation. PR 3 therefore adds an empirical Young/Seeley excess loss.

The reference model uses the familiar viscous and separation terms

```text
Kv = 32 (0.83 Ls + 1.64 Ds) / D0 * (A0 / As)^2
Kt = 1.52
```

with the corresponding pressure-loss dependence on `Q` and `Q|Q|`.

VascuQuest does **not** simply add the full empirical formula on top of the native 1-D equations. The PR-2 solver already contains ordinary-vessel viscous friction and fluid inertia. To avoid double counting:

1. the unstenosed Young/Seeley viscous contribution is subtracted from the stenosed viscous coefficient;
2. the separation term is added as an excess disease loss;
3. the original empirical inertial term is not added a second time because fluid inertia is already present in the 1-D momentum equation.

The resulting local loss is distributed across the lesion with spatial weights whose integral is exactly one. Its sign follows the flow direction, so it opposes both forward and reverse flow.

Scientific source: Seeley BD, Young DF. *Effect of geometry on pressure losses across models of arterial stenoses*. Journal of Biomechanics. 1976;9(7):439-448. DOI `10.1016/0021-9290(76)90086-5`.

## Fusiform abdominal aortic aneurysm

The v1 AAA preset applies a smooth fusiform dilation over the frozen main abdominal-aortic path. `maximum_diameter_m` is interpreted as an absolute model-space lumen diameter.

The requested aneurysm must:

- fit completely inside the frozen abdominal-aortic path; and
- have a requested maximum diameter greater than the healthy diameter everywhere covered by the requested aneurysm region.

Reference area, PWDB wall stiffness and source Voigt-wall coefficients are then recalculated from the transformed local radius using the same constitutive relations used by the PR-2 solver.

No separate empirical aneurysm pressure-loss term is introduced in PR 3. The 1-D solver propagates the consequences of the smooth geometric dilation, but v1 does **not** represent three-dimensional aneurysm vortices, recirculation, intraluminal thrombus, wall thickness, asymmetric sac geometry, rupture mechanics, or remodelling.

## Large-artery stiffening

The preset parameter `target_cfpwv_m_per_s` is implemented as a **model-space carotid-femoral characteristic PWV target**, not as a simulated clinical tonometry procedure.

The baseline value is calculated from the differential characteristic travel distance and travel time between frozen left carotid and left femoral paths. At the diastolic reference state, wave speed follows the same PR-2 pressure-area law. The target is achieved by uniformly scaling `beta` over the frozen bilateral large-conduit segment set by

```text
beta scale = (target model cfPWV / baseline model cfPWV)^2
```

because characteristic wave speed is proportional to `sqrt(beta)` at fixed reference area and density.

The transform:

- rejects targets below the subject's baseline model-space cfPWV because that would be softening, not stiffening;
- leaves reference geometry unchanged;
- leaves the source Voigt wall-viscosity coefficient unchanged;
- leaves cardiac inflow and terminal beds unchanged.

## Parent-state immutability

No transformation mutates the healthy PWDB state. In particular, PR 3 does not overwrite:

- source segment lengths or radii;
- source model-configuration values;
- aortic-root inflow;
- age, heart rate or stroke volume;
- terminal Windkessel parameters;
- canonical PWDB subject identity.

Only the separate transformed solver model carries disease causality.

## Disease-aware solver

`DiseaseOneDSolver` is separate from `NativeOneDSolver`. The healthy Gate-0 solver therefore remains unchanged.

The disease solver reuses the PR-2 finite-volume fluxes, wall law, Voigt source, junction coupling, terminal boundaries, time integration and convergence machinery. It adds only the explicit local excess pressure-loss source required by transformed focal stenoses.

Fast verification checks include:

- exact source-anatomy target mappings;
- zero-stenosis no-op behaviour;
- signed and severity-sensitive Young/Seeley excess loss;
- focal target-only geometry changes;
- iliac execution on the frozen source segment;
- AAA changes restricted to the frozen abdominal-aortic path;
- rejection of a non-dilating AAA request;
- exact model-space cfPWV target identity under stiffening;
- rejection of softening through the stiffening preset;
- preservation of a zero-flow/reference-pressure equilibrium even when a local disease-loss term is present.

These are software and mechanistic-model verification tests. They are not clinical validation.

## Critical qualification boundary

PR 2 deliberately left healthy PWDB reconstruction at:

```text
METRICS_ONLY_THRESHOLDS_NOT_FROZEN
```

PR 3 does not change that state and does not tune any disease parameter to reduce healthy reconstruction error.

Therefore the existence of executable disease transformations does **not** yet authorise a production disease-population claim. Real-source healthy reconstruction tolerances and the later disease credibility/qualification programme remain mandatory before production use.

## PR 3 non-goals

PR 3 contains no:

- public runtime virtual-disease dataset;
- generated disease population through `DatasetSession`;
- disease-qualified `ScientificResult` vectors;
- public disease exporter;
- public disease-generation CLI;
- Doppler-ultrasound simulation;
- clinical diagnostic classification;
- claim that the four disease models reproduce real patients.

Those remain gated behind subsequent implementation and validation stages.

## Gate for PR 4

PR 4 may materialise a disease-transformed subject/population only after this PR is manually reviewed and merged. It must preserve the parent PWDB identity, causal disease specification, solver provenance, quantity-status classification and `MODELLED` evidence boundary. PR 4 must not silently upgrade the scientific credibility of PR-3 transformations.
