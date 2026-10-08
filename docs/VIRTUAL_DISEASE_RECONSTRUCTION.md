# Virtual Disease healthy reconstruction and forward-solver foundation

## 1. Purpose

Virtual Disease requires an independent healthy cardiovascular reconstruction before any disease transformation is applied. The purpose is to ensure that disease parameters represent causal interventions rather than hidden calibration knobs used to compensate for an inaccurate healthy baseline.

The healthy reconstruction layer is part of the completed VascuQuest 1.0 Virtual Disease subsystem. It is not a future/staged capability.

## 2. Scientific boundary

The healthy parent state is an immutable solver-ready representation of one canonical PWDB virtual subject assembled from verified source artifacts.

The reconstruction layer:

- preserves canonical PWDB subject identity;
- reads source/configuration values needed by the disease solver;
- preserves source arterial topology and geometry;
- reconstructs the healthy aortic inflow from source waveforms;
- propagates the healthy state through the first-party 1-D cardiovascular solver;
- provides the baseline against which disease transformations operate.

It does not modify canonical PWDB artifacts and does not turn the reconstructed subject into a clinical patient model.

## 3. Baseline assembly

`PWDBBaselineAssembler` consumes an existing canonical PWDB `DatasetSession` and trusted artifact access. The solver-ready healthy state includes, as required by the model:

- canonical subject identity;
- source age and cardiac timing/flow inputs;
- heart rate, stroke volume, LVET, and peak-flow timing;
- blood density and viscosity;
- momentum/friction parameters used by the source-compatible model;
- pressure/outlet/systemic-resistance inputs;
- PWDB wall stiffness coefficients;
- PWDB Voigt-wall coefficients;
- all source-defined arterial segment lengths, inlet/outlet radii, and topology;
- source terminal resistance/compliance parameters.

Some solver-specific configuration fields are accessed through bounded disease-private readers over the same checksum-verified PWDB artifacts. This does not widen or redefine the public PWDB scientific schema.

## 4. Preserved aortic inflow

Healthy inlet forcing is reconstructed from the canonical PWDB aortic-root velocity and area waveforms:

```text
Q(t) = U(t) A(t)
```

This preserves the selected virtual subject's original cardiac forcing for the arterial disease experiments.

The four frozen v1 disease presets are arterial interventions and do not introduce a new cardiac-flow generator.

## 5. One-dimensional cardiovascular model

The first-party solver retains the source-compatible one-dimensional compliant-artery model, including:

- conservation of arterial cross-sectional area/mass;
- conservation of momentum;
- subject-specific tapered arterial geometry;
- square-root pressure-area (`beta`) wall relation;
- source-compatible radius/stiffness parameterization;
- Voigt wall-viscoelastic contribution where represented by the model;
- blood-friction/source terms;
- prescribed aortic volumetric-flow inlet;
- arterial junction coupling;
- terminal RCR/Windkessel beds.

The numerical discretization is an implementation choice and does not redefine PWDB source physiology.

## 6. Reference implementation

The NumPy implementation is the reference/default Virtual Disease backend.

The network solver uses the documented finite-volume disease implementation and converges the system to a periodic cardiac-cycle state under its numerical controls. Solver execution identity is preserved so a persisted result can be tied to the exact numerical route used.

## 7. Optional JAX backend

VascuQuest also provides an optional JAX execution backend for the same declared disease model. The JAX backend is optional and isolated behind the `jax` extra.

Its qualification is evidence-based and scope-specific. VascuQuest does not generalize the available JAX qualification into unsupported claims about GPU microbatch equivalence, clinical validity, or empirical full-network convergence order beyond what is recorded by its evidence.

The NumPy reference behavior remains the scientific baseline for the disease model.

See [`JAX_VIRTUAL_DISEASE_QUALIFICATION.md`](JAX_VIRTUAL_DISEASE_QUALIFICATION.md) and the frozen machine-readable certificate in `docs/evidence/` for the exact qualified lineage.

## 8. Healthy no-intervention logic

A healthy reconstruction is conceptually distinct from a disease no-op. Disease transforms must reduce exactly to the healthy model when their intervention parameter is defined as zero/no-op.

This property prevents a “zero disease” request from changing geometry or introducing artificial loss.

## 9. Numerical verification

Fast numerical tests exercise fundamental model invariants independently of source-output agreement. Examples include:

- pressure-area forward/inverse consistency;
- physically admissible positive stiffness/area states;
- terminal-bed equilibrium behavior;
- junction/boundary consistency;
- finite solver output;
- stable zero/steady reference states;
- deterministic execution identity.

These tests are necessary but are not, by themselves, clinical validation.

## 10. Reconstruction qualification and frozen evidence labels

Healthy reconstruction qualification compares the independent solver output with source-supported PWDB haemodynamic behavior using the documented reconstruction metrics/gates.

A critical documentation rule applies here:

> Qualification-state labels belong to the exact evidence lineage that recorded them. Documentation must neither silently upgrade them nor present a frozen historical label as though it describes every current VascuQuest 1.0 capability.

For example, the JAX and parameterized-cohort qualification records preserve the label:

```text
METRICS_ONLY_THRESHOLDS_NOT_FROZEN
```

because that is part of their frozen evidence contract. It must remain unchanged inside those qualification records and persisted bundles where recorded.

That label does **not** mean that Virtual Disease, HEMOSPACE, or the v1 analysis stack is unfinished. VascuQuest 1.0 has a completed mechanistic Virtual Disease implementation with explicit qualification boundaries; the frozen label specifically states the reconstruction-threshold status carried by that evidence lineage.

A reconstruction metric is evidence about agreement with the source model; it is not evidence that PWDB itself is a clinical patient model.

## 11. Disease separation rule

Disease transformations are applied only after the healthy parent state has been assembled. A disease transform receives:

```text
healthy BaselineCardiovascularState
+ DiseaseSpecification
→ DiseasePhysicsModel
```

The healthy parent remains unchanged. Disease geometry/wall/loss changes live in the separate modelled disease state.

## 12. Geometry and topology

The healthy model uses the source 116-segment arterial network. Disease targeting operates on canonical arterial segment identity, not on the smaller set of common waveform measurement sites.

This distinction prevents measurement-site labels from being repurposed as anatomical disease definitions.

## 13. Boundary and terminal behavior

The forward model includes explicit inlet, junction, and terminal-bed behavior. Terminal parameterization belongs to the healthy solver-ready subject state and is propagated consistently into disease calculations unless the disease specification explicitly modifies the relevant model parameter.

Downstream v1 analysis code cannot modify these boundary/terminal equations.

## 14. Reproducibility

A healthy reconstruction/disease experiment should retain:

- parent PWDB dataset identity;
- canonical subject ID;
- source artifact/checksum provenance;
- solver/backend execution identity;
- numerical scheme/version where relevant;
- reconstruction qualification state exactly as recorded by the applicable evidence/bundle;
- warnings/assumptions;
- VascuQuest version.

## 15. Interaction with v1 analysis

`vascuquest.analysis`, `stats`, `mechanics`, `spectral`, and `plot` operate only after scientific results have been materialized. They do not call the reconstruction solver as an implicit side effect.

Thus an already persisted disease/healthy result can be analyzed repeatedly without repeating healthy reconstruction or network integration.

Downstream results remain provenance-connected to the reconstruction/model inputs. A derived mechanics/spectral/statistical result cannot erase the fact that its disease-state upstream input was `MODELLED`.

## 16. Non-claims

Healthy reconstruction does not establish:

- patient-specific physiological validity;
- clinical calibration;
- three-dimensional haemodynamics;
- measured wall material properties;
- clinical boundary-condition validity;
- epidemiological representativeness;
- longitudinal biological evolution across PWDB ages.

Its purpose is narrower: provide a reproducible independent healthy model state suitable as the parent of the declared mechanistic Virtual Disease interventions.

## 17. Related documentation

- [`VIRTUAL_DISEASE.md`](VIRTUAL_DISEASE.md)
- [`VIRTUAL_DISEASE_PHYSICS.md`](VIRTUAL_DISEASE_PHYSICS.md)
- [`VIRTUAL_DISEASE_RUNTIME.md`](VIRTUAL_DISEASE_RUNTIME.md)
- [`JAX_VIRTUAL_DISEASE_QUALIFICATION.md`](JAX_VIRTUAL_DISEASE_QUALIFICATION.md)
- [`PARAMETERIZED_COHORT_QUALIFICATION.md`](PARAMETERIZED_COHORT_QUALIFICATION.md)
- [`TEST_VALIDATION_CONTRACT.md`](TEST_VALIDATION_CONTRACT.md)
