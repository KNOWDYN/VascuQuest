# Mechanical-closure kinematics

## Scope

`vascuquest.kinematics` extends the exact axisymmetric kinematic lift with a general mechanical-closure analysis layer. The extension consumes an existing `KinematicLift`; it does not alter the lift equations, PWDB, HEMOSPACE semantics, or Virtual Disease physics.

The primary pipeline is

```text
P(z,t), U(z,t), A(z,t), rho, mu, t
        ↓
exact axisymmetric KinematicLift
        ↓
grad(u), S, Omega, Q
        ↓
K, ell=u×omega, L=omega×u, q_H
        ↓
wall traction, C_U, C_H, C_D
        ↓
near-wall Lamb loading
        ↓
m*=[Q*, q_H*, C_U*, C_H*, C_D*]
        ↓
d_tau, d_M, hydrodynamic-degeneracy classification
```

This is deterministic post-processing. It does not run CFD or FSI.

## Exactness boundary

The existing lift remains exact under its declared axisymmetric, no-swirl, incompressible, parabolic-profile and circular-equivalent-radius axioms.

Within that lifted field:

- cylindrical radial derivatives are evaluated analytically from the exact polynomial dependence on `q=r/R`;
- `grad(u)`, `S`, `Omega`, `Q`, the Lamb vector and full Newtonian wall traction are direct differential consequences of the lift;
- hydrodynamic charge is evaluated independently by both `div(omega×u)` and `-2Q-laplacian(K)`;
- the Crocco terms are constructed independently and are never solved by forcing the closure residual to zero.

Path derivatives remain numerical because source fields are stored at discrete physical path positions. Mechanical-closure quantities that introduce an effective third source derivative require at least four stored positions inside an anatomical differentiation run. Shorter runs are explicitly masked; derivatives never cross declared artery boundaries.

## Pressure and time

The general Python API `mechanical_state(...)` accepts pressure in pascals and requires an explicit physical time vector.

The HEMOSPACE bridge reads canonical path-resolved `P/U/A`. The authoritative path exporter stores pressure in mmHg, so `mechanical_state_from_path_waves(...)` converts it explicitly to pascals before the mechanical-head calculation.

The pressure lift is

```text
p(r,z,t) = P(z,t)
```

which is an explicit one-dimensional source-model axiom. Pressure is not reconstructed from the Crocco relation.

## Level I: strain-rotation topology

`strain_rotation_topology(field)` returns the non-zero cylindrical velocity-gradient components, strain and rotation components, and

```text
Q = 0.5 * (Omega:Omega - S:S)
```

on `(path_position, time, radial_fraction)`.

## Level II: Lamb vector and hydrodynamic charge

`lamb_hydrodynamic_charge(field)` uses the convention

```text
ell = u × omega
L   = omega × u = -ell
```

and returns both

```text
q_H_divergence = div(L)
q_H_identity   = -2 Q - laplacian(K)
```

plus the independent identity residual

```text
R_q = q_H_divergence + 2 Q + laplacian(K).
```

The two routes share the source field but not the defining algebra for `q_H`, so the residual is a genuine implementation/discretization check.

## Complete Newtonian wall traction

`wall_traction(field, mu)` evaluates

```text
tau = 2 mu S
wall traction = (I - n n) tau n
```

using the local wall slope `R_z`. The returned signed tangent component, radial/axial vector components and magnitude are the reference wall-shear description for closure analysis. The implementation does not replace the complete traction by the straight-tube scalar shortcut `4 mu U/R`.

## Generalized Crocco decomposition

`crocco_decomposition(...)` independently constructs

```text
C_U = partial(u)/partial(t)
C_H = grad(P/rho + K + Phi)
C_D = -nu laplacian(u)
ell = C_U + C_H + C_D + residual
```

for constant positive density and Newtonian dynamic viscosity. `Phi` is optional and is represented as a cross-section-uniform conservative potential head.

The result also exposes:

- `D_U`, `D_H`, `D_D` magnitude fractions;
- cancellation index `chi_C`;
- nonlinear-unsteady magnitude balance `B_LU`;
- Lamb/unsteady directional alignment `A_LU`;
- the direct vector residual and normalized closure residual.

The activity threshold is supplied explicitly in acceleration units or, through `mechanical_state(...)`, as a declared fraction of `U_c^2/L_c`.

## Near-wall Lamb loading

`radial_shell_lamb_load(...)` evaluates the signed areal Lamb load over an axisymmetric local radial shell

```text
q in [1-delta*, 1].
```

The signed radial, axial and local wall-normal components use analytic integration of the exact Lamb polynomials and have units of pascals. The non-cancelling absolute normal load uses fixed Gauss-Legendre quadrature of those same exact polynomials.

For `R_z=0` the radial shell is a strict wall-normal shell. For a sloped wall it remains an explicitly defined radial-shell control volume; VascuQuest does not silently introduce interpolation in `z` to pretend that it is a strict normal-thickness construction.

## Dimensionless mechanical state

`mechanical_state(...)` requires predeclared positive characteristic scales `U_c` and `L_c` and constructs

```text
a_c = U_c^2/L_c
q_c = U_c^2/L_c^2
Q*   = Q/q_c
q_H* = q_H/q_c
C_j* = C_j/a_c
```

for `j in {U,H,D}`.

Derived Crocco/Lamb balance quantities are retained for interpretation but are not added as independent coordinates of the primary state.

## Closure distances

`wall_shear_distance(...)`, `mechanical_state_distance(...)`, and `closure_comparison(...)` implement the computational distance layer.

Cross-geometry mapping is deliberately not invented. Callers must supply explicit positive quadrature/correspondence weights:

- `wall_weights` for the mapped wall domain;
- `volume_weights` for the mapped near-wall volume.

This keeps the one-to-one wall/domain correspondence outside the metric itself and prevents hidden interpolation or an arbitrary choice of one geometry as the reference measure.

Thresholds `epsilon_tau` and `epsilon_mechanical` are optional. When supplied, `closure_comparison(...)` reports whether a pair is shear-equivalent, mechanically equivalent, and whether it satisfies the hydrodynamic-degeneracy condition.

## Independent certificate

`certify_mechanical_state(...)` reports:

1. the normalized `q_H + 2Q + laplacian(K)` residual;
2. the generalized Crocco normalized residual;
3. the `D_U + D_H + D_D = 1` partition error;
4. qualified and masked path counts.

The certificate evaluates independent identities. It never uses an identity to manufacture the term that the same identity is meant to verify.

## Analytical regression benchmark

The permanent test suite includes steady Poiseuille flow in a rigid circular tube. It verifies exactly that:

- `Q=0`;
- full wall traction reduces to `4 mu U/R`;
- the hydrodynamic-charge identity closes;
- the independently constructed Crocco decomposition closes;
- the near-wall signed Lamb load matches its closed-form integral.

A paired Poiseuille regression also uses

```text
A: R=4 mm, U=0.30 m/s
B: R=8 mm, U=0.60 m/s
```

with identical `mu` and `rho`. The pair has identical wall shear because `U/R` is identical, but the near-wall Lamb load differs by a factor of four. With explicit correspondence weights and predeclared thresholds, the test must classify this pair as shear-equivalent and mechanically non-equivalent.

## Python API

```python
import numpy as np
import vascuquest as vq

hs = vq.hemospace.open_hemospace(source="/path/to/pwdb", offline=True)
waves = vq.kinematics.path_waves_from_hemospace(
    hs, "1", "aorta_foot", signals=("P", "U", "A")
)

dt = 0.001  # must come from an independently known source timing contract
time_s = np.arange(waves.matrix("U").shape[1]) * dt

state = vq.kinematics.mechanical_state_from_path_waves(
    waves,
    time_s,
    density_kg_m3=1050.0,
    dynamic_viscosity_pa_s=0.004,
    velocity_scale_m_s=0.5,
    length_scale_m=0.01,
    radial_points=33,
    thickness_fraction=0.10,
)
certificate = vq.kinematics.certify_mechanical_state(state)
```

Density, viscosity, characteristic scales and timing are intentionally explicit; the API does not insert physiological defaults.

## CLI

```bash
vascuquest kinematics mechanical-state \
  --subject 1 \
  --path aorta_foot \
  --source /path/to/pwdb \
  --offline \
  --sample-period-s 0.001 \
  --density-kg-m3 1050 \
  --viscosity-pa-s 0.004 \
  --velocity-scale-m-s 0.5 \
  --length-scale-m 0.01 \
  --output mechanical-state.npz
```

Use `vascuquest kinematics mechanical-certify` with the same physical inputs to run the independent certificate without exporting the state.

## Interpretation boundary

Mechanical-closure outputs are `DERIVED` from source/reconstructed fields. They are not measured 3D haemodynamics, biological response variables, clinical predictions, or unrestricted three-dimensional flow fields. The extension tests mechanical sufficiency inside the declared axisymmetric lifted flow class.
