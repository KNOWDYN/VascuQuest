# Virtual Disease healthy reconstruction

## PR 2 status

This document describes implementation stage 2 of 5 for the first-party VascuQuest Virtual Disease subsystem.

PR 2 adds the **healthy reconstruction and forward-solver foundation only**. It does not impose any disease condition, generate a diseased population, create a runtime disease backend, or expose a disease-generation CLI.

## Purpose

Before a disease transformation can be trusted, VascuQuest must be able to reconstruct an unchanged PWDB virtual subject and propagate that subject through an independent cardiovascular solver. Disease parameters must never be used to compensate for baseline solver error.

The PR therefore introduces two separate capabilities:

1. assembly of one immutable, solver-ready healthy PWDB cardiovascular state from already verified canonical artifacts; and
2. an independent NumPy implementation of the one-dimensional compliant-artery forward model used to calculate a complete arterial pressure/flow/area state.

The existing canonical PWDB backend, canonical schema, public `DatasetSession`, derivations, exporters and CLI remain unchanged.

## Baseline assembly

`PWDBBaselineAssembler` accepts an existing canonical PWDB `DatasetSession` and the existing `ArtifactAcquirer`. It reads only source inputs needed by the solver:

- exact canonical subject identity;
- age, heart rate, stroke volume, LVET and peak-flow timing;
- blood density and viscosity;
- momentum correction parameter;
- diastolic, mean and outlet pressure inputs;
- systemic peripheral resistance;
- PWDB wall stiffness coefficients `k1`, `k2`, `k3`;
- PWDB Voigt wall coefficients `b0`, `b1`;
- all source-provided arterial segment lengths, inlet/outlet radii and topology;
- source terminal resistance and compliance values.

Parameters not exposed through the ordinary public VascuQuest schema are read through a disease-private bounded reader from the same checksum-verified `model_configurations` artifact. This does not widen or modify the canonical PWDB backend.

## Preserved aortic inflow

The healthy inlet forcing is reconstructed directly from the canonical PWDB aortic-root source waveforms:

```text
Q(t) = U(t) A(t)
```

This is appropriate for Gate 0 because it preserves the selected virtual subject's original cardiac forcing exactly. The four frozen v1 disease presets are arterial interventions and do not modify cardiac inflow.

No new cardiac-flow generator is introduced in this stage.

## Native one-dimensional solver

The solver is a first-party NumPy implementation and does not require MATLAB or Nektar1D at VascuQuest runtime.

It retains the PWDB-compatible causal model:

- conservation of arterial cross-sectional area/mass;
- conservation of momentum;
- subject-specific tapered arterial geometry;
- PWDB/Nektar square-root pressure-area (`beta`) wall law;
- PWDB `Eh(k1,k2,k3,Rd)` stiffness relation;
- PWDB source Voigt-wall `Gamma` relation;
- blood-friction source term;
- aortic volumetric-flow inlet;
- characteristic coupling at arterial junctions;
- three-element RCR/Windkessel terminal beds.

The numerical implementation uses conservative finite-volume integration with MUSCL reconstruction, an HLL-type interface flux, SSP-RK2 time stepping, CFL/diffusive stability control and cycle-to-cycle periodic convergence.

The discretisation is an implementation choice. It does not redefine the PWDB physiological model.

## Numerical verification

Fast synthetic tests exercise model invariants independently of PWDB output agreement. In particular, a vessel supplied with zero inflow and outlet pressure equal to its reference diastolic pressure must remain at zero flow and reference pressure rather than spontaneously generating a pulse.

Additional checks cover:

- pressure-area inversion;
- tapered reference-state pressure consistency;
- positive stiffness coefficients;
- terminal Windkessel equilibrium;
- finite solver output;
- cycle convergence;
- terminal mass balance;
- bounded source-configuration parsing.

These are numerical/software verification checks, not clinical validation.

## Gate 0 reconstruction evidence

`HealthyReconstructionValidator` compares the solver's final healthy cycle against canonical PWDB common-site source waves at all 13 exported sites:

| Site | PWDB segment | Axial fraction |
|---|---:|---:|
| AorticRoot | 1 | 0.00 |
| ThorAorta | 18 | 1.00 |
| AbdAorta | 39 | 0.00 |
| IliacBif | 41 | 1.00 |
| Carotid | 15 | 0.50 |
| SupTemporal | 87 | 1.00 |
| SupMidCerebral | 72 | 1.00 |
| Brachial | 21 | 0.75 |
| Radial | 22 | 1.00 |
| Digital | 112 | 1.00 |
| CommonIliac | 44 | 0.50 |
| Femoral | 46 | 0.50 |
| AntTibial | 49 | 1.00 |

For each site the validator compares:

```text
P
U
A
Q = U*A
```

and records, without applying a qualification threshold:

- normalized RMSE;
- relative mean error;
- peak relative error;
- trough relative error;
- circular phase error.

## Qualification state

PR 2 intentionally permits exactly one Gate-0 qualification state:

```text
METRICS_ONLY_THRESHOLDS_NOT_FROZEN
```

No `PASS`, `VALIDATED`, or equivalent state exists in this implementation stage.

Real-source reconstruction results must be inspected before numerical acceptance tolerances are frozen. A solver that executes successfully is not thereby proven to reproduce PWDB sufficiently closely for disease generation.

## PR 2 non-goals

PR 2 contains no:

- carotid-stenosis transformation;
- iliac-stenosis transformation;
- aneurysm transformation;
- arterial-stiffening transformation;
- Young-Seeley disease pressure-loss term;
- runtime virtual-disease dataset;
- disease-qualified runtime vectors;
- virtual-disease population generation;
- disease CLI command;
- clinical validation claim.

Those remain gated behind subsequent PRs.

## Gate for PR 3

PR 3 may add the frozen disease transformations only on top of this healthy reconstruction layer. Disease transformations must not be tuned to cancel healthy reconstruction errors. Full production validity still requires the later real-source qualification workflow and the complete four-layer credibility programme.
