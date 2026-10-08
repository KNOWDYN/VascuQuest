# Spectral and arterial-wave analysis

## Canonical v1 methods

- one-sided DFT harmonic amplitude and phase;
- periodogram PSD and normalized spectral entropy;
- explicit high/low harmonic-energy ratios;
- cross-spectral density magnitude/phase;
- magnitude-squared coherence, including cross-site signals for the same virtual subject;
- H1 transfer function `Sxy/Sxx`;
- pressure-flow input impedance `Z_n=P_n/Q_n`;
- characteristic-impedance estimate over an explicit harmonic interval;
- pulsatile pressure wave separation using an explicit `Zc`;
- explicit-Zc reflection magnitude;
- net/forward/backward wave-intensity rate using explicit local wave speed and blood density;
- STFT magnitude;
- continuous wavelet-transform magnitude when PyWavelets is installed;
- path-wise harmonic-amplitude evolution.

## Sampling contract

Frequency-domain operations require a finite, one-dimensional, strictly increasing and uniformly sampled native time coordinate. VascuQuest does not interpolate or silently resample. Cross-site operations still require the same subject and aligned time base.

## Denominator protection

Impedance or transfer-function frequencies below declared denominator thresholds are reported as undefined rather than numerically inflated.

## Wave-analysis boundary

Wave separation requires an explicit characteristic impedance. Wave-intensity separation requires explicit wave speed. VascuQuest does not silently infer either parameter inside those operations.

## Scientific references

- AHA arterial-stiffness standardization statement: `10.1161/HYP.0000000000000033`.
- Alastruey et al., arterial pressure/flow wave analysis with 1-D haemodynamics, PMID 25138163.
- European Heart Journal review of pulsatile arterial haemodynamics and wave intensity: `10.1093/eurheartj/ehy346`.
