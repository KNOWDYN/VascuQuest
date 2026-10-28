# Cardioacoustics

`vascuquest.cardioacoustics` is an analytical frequency-domain extension for studying endogenous cardiohemic vibration as a mechanical input to the arterial endothelium.

The module intentionally does **not** reinterpret PWDB high-order haemodynamic harmonics as heart sounds. Cardioacoustic excitation is supplied independently as a provenance-bearing root pressure spectrum. VascuQuest supplies the virtual arterial geometry, blood properties and healthy or Virtual Disease wall state.

## Physical model

For each locally uniform arterial cell, VascuQuest combines the exact Womersley relation for oscillatory flow in a circular tube with the linearised PWDB/Nektar elastic-Voigt wall law. With phasor convention `Re[p exp(i omega t)]`,

\[
C_A^*(\omega)=\left[\frac{\beta}{2A_0}+i\omega\frac{\Gamma}{\sqrt{A_0}}\right]^{-1}.
\]

The Womersley flow factor is

\[
F(\alpha)=1-\frac{2J_1(\lambda)}{\lambda J_0(\lambda)},\qquad
\lambda=i^{3/2}\alpha.
\]

The distributed series impedance and shunt admittance are

\[
Z_\ell=\frac{i\omega\rho}{A_0F},\qquad
Y_\ell=i\omega C_A^*.
\]

Hence

\[
\gamma=\sqrt{Z_\ell Y_\ell},\qquad
k=-i\gamma,\qquad
Z_c=\sqrt{\frac{Z_\ell}{Y_\ell}}.
\]

This is an analytical coupled blood-wall mode. It is not a bulk-fluid acoustic wave at approximately 1500 m/s and it is not a CFD or numerical FSI model.

## Endothelial receiver

At any axial position the solved pressure field is mapped to four phasors: pressure, volume flow, tangential traction and radial wall displacement. The endothelial outputs used by the research programme are therefore

\[
\hat p_{EC}(\omega),\qquad
\hat\tau_{EC}(\omega),\qquad
\hat\eta_w(\omega).
\]

The wall displacement follows directly from the complex area compliance. Tangential traction is evaluated from the analytical Womersley velocity gradient at the wall and recovers the Poiseuille wall-shear result in the low-Womersley limit.

## pyva backend

Network assembly uses the optional MIT-licensed `pyva-toolbox` backend. Each VascuQuest arterial mesh cell is solved analytically and its transfer matrix is cascaded across the parent arterial segment. The complete heterogeneous segment is then reduced exactly to a two-port pressure/volume-flow admittance and inserted into pyva as a `DynamicMatrix`. pyva therefore supplies DOF-aware network assembly and branching-junction bookkeeping; it does not define the arterial physics. Collapsing each arterial segment to one two-port keeps the global solve at arterial-network scale instead of exposing every disease-solver cell as a global acoustic node.

The current v1 network backend imposes the cardiohemic root pressure spectrum exactly and uses matched terminal impedances. This isolates wall-state effects without claiming that low-frequency PWDB Windkessel parameters are valid acoustic terminations in the S1/S2 band.

Install the optional backend with:

```bash
pip install "vascuquest[cardioacoustics]"
```

`pyva-toolbox` requires Python 3.12 or later. The analytical local functions remain importable on Python 3.11, but the network backend will raise `CapabilityError` when pyva is unavailable.

## Minimal Python use

```python
import numpy as np
from vascuquest.cardioacoustics import (
    CardioacousticSourceSpectrum,
    arterial_mode_spectrum,
    solve_pyva_network,
)

source = CardioacousticSourceSpectrum.from_amplitude_phase(
    frequency_hz=np.array([20.0, 40.0, 80.0, 120.0]),
    amplitude_pa=np.array([1.0, 1.0, 0.6, 0.3]),
    phase_rad=np.zeros(4),
    source_identity="literature-bounded:S1S2-example",
)

# Local analytical mode
mode = arterial_mode_spectrum(
    source.frequency_hz,
    area_m2=3.0e-4,
    beta_pa=2.0e5,
    gamma_pa_s_per_m=2.0e5,
    density_kg_per_m3=1060.0,
    viscosity_pa_s=0.004,
)

# Population/network analysis uses a reconstructed BaselineCardiovascularState
# and optionally a Virtual Disease NetworkDiscretization:
# solution = solve_pyva_network(baseline, source, network=disease_model.network)
```

## Scientific boundary

This module establishes physical plausibility and falsifiable spectral predictions. It does not by itself establish that endothelial cells biologically respond to the predicted endogenous signal. Biological mechanosensory thresholds and signalling responses remain independent evidence.
