# Spectral and wave analysis in VascuQuest 1.0

## 1. Scope

`vascuquest.spectral` provides qualified arterial waveform analysis over existing VascuQuest `Waveform` objects. It is a post-processing layer and does not rerun the vascular-network solver.

The v1 namespace covers:

- Fourier harmonics;
- power spectral density;
- cross-spectral density;
- coherence;
- transfer functions;
- pressure-flow input impedance;
- characteristic-impedance estimates;
- forward/backward wave separation;
- reflection magnitude;
- wave-intensity analysis;
- spectral entropy;
- harmonic-energy ratios;
- STFT;
- continuous wavelet magnitude;
- path-wise harmonic evolution.

## 2. Core input contract

A spectral input is a VascuQuest `Waveform` with:

- explicit subject identity;
- explicit vascular location;
- explicit time coordinate;
- finite waveform values required by the method;
- supported physical units.

Methods that rely on FFT/Welch/STFT sampling assume a uniformly sampled native time coordinate and verify it. Hidden interpolation/resampling is forbidden.

## 3. Pairing and location rules

For two-waveform methods, the scientific relationship determines the admissibility rule.

### Local haemodynamic relations

Pressure-flow impedance, characteristic impedance, pressure-flow wave separation, reflection magnitude, and pressure-velocity wave intensity require the signals to describe the **same subject and same vascular location** on an aligned time base.

### Cross-site signal relations

CSD, coherence, and transfer functions may compare different vascular locations for the same virtual subject if their time coordinates are aligned. These methods describe signal relationships across locations; they do not imply causality.

## 4. Unit normalization

Pressure-flow methods normalize pressure to Pa and flow to m³/s. Wave-intensity analysis normalizes velocity to m/s.

Frequency coordinates are reported in Hz. Phase quantities are reported in radians.

## 5. Harmonic amplitude

`harmonic_amplitude(waveform, n_harmonics=...)` computes the one-sided discrete Fourier representation according to the v1 normalization convention.

The result is indexed by harmonic number and frequency.

Use cases include:

- arterial pressure/flow harmonic structure;
- disease-vs-healthy harmonic response;
- path-wise harmonic attenuation/amplification;
- inputs to impedance descriptors.

CLI:

```text
vascuquest spectral harmonics waveform.json --count 10
```

## 6. Harmonic phase

`harmonic_phase(...)` returns the phase angle of the selected Fourier harmonics under the same convention as harmonic amplitude.

CLI:

```text
vascuquest spectral harmonics waveform.json --count 10 --phase
```

Phase must always be interpreted relative to the declared Fourier/time convention. Cross-study comparison requires consistent definitions.

## 7. Power spectral density

`power_spectral_density(...)` computes a qualified spectral-power representation of a uniformly sampled waveform.

CLI:

```text
vascuquest spectral psd waveform.json
```

PSD describes distribution of waveform variance/energy across frequency. It does not create new physiological source measurements.

## 8. Cross-spectral density

`cross_spectral_density(x, y, ...)` describes the complex shared frequency structure between two aligned waveforms.

The public CLI can return magnitude or phase:

```text
vascuquest spectral csd x.json y.json
vascuquest spectral csd x.json y.json --phase
```

Cross-site use is permitted when the waveforms are from the same subject and have aligned time bases.

## 9. Coherence

`coherence(x, y, nperseg=...)` estimates frequency-dependent normalized linear association between aligned waveforms.

CLI:

```text
vascuquest spectral coherence x.json y.json --nperseg 64
```

Important boundary:

> High coherence does not prove causal transmission or a physiological mechanism. It quantifies the implemented frequency-domain association.

## 10. Transfer function

`transfer_function(input_waveform, output_waveform, ...)` estimates a frequency-domain input-output ratio under the implemented spectral estimator.

CLI:

```text
vascuquest spectral transfer proximal.json distal.json
vascuquest spectral transfer proximal.json distal.json --phase
```

Cross-site transfer functions are descriptive/model-based frequency relationships unless a separate causal system-identification interpretation is justified.

## 11. Pressure-flow input impedance

Method:

```text
vascuquest:spectral:input-impedance-v1
```

For aligned local pressure and flow, after removal of the mean component:

```text
Z_n = P_n / Q_n
```

The v1 method returns:

- impedance magnitude `|Z_n|` in `Pa·s/m³`;
- phase `arg(Z_n)` in rad;
- harmonic and frequency coordinates.

The method ignores/marks undefined harmonics when the flow coefficient magnitude is below the declared denominator threshold.

CLI:

```text
vascuquest spectral impedance pressure.json flow.json --harmonics 10
vascuquest spectral impedance pressure.json flow.json --harmonics 10 --phase
```

## 12. Characteristic-impedance estimate

Method:

```text
vascuquest:spectral:characteristic-impedance-v1
```

The v1 estimator computes the median impedance magnitude over an explicitly selected higher-harmonic range.

Default CLI concept:

```text
vascuquest spectral characteristic-impedance pressure.json flow.json --start 3 --end 10
```

Important warning:

> This is a method-dependent frequency-domain estimate. It is not a directly measured wall material property.

## 13. Pressure-flow wave separation

Method:

```text
vascuquest:spectral:wave-separation-v1
```

Given local pulsatile pressure `P'`, flow `Q'`, and an explicit characteristic impedance `Zc`:

```text
P_forward  = 0.5 (P' + Zc Q')
P_backward = 0.5 (P' - Zc Q')
```

Mean pressure/flow components are removed before separation in the v1 method.

CLI:

```text
vascuquest spectral wave-separation pressure.json flow.json <ZC>
vascuquest spectral wave-separation pressure.json flow.json <ZC> --backward
```

The result inherits the supplied `Zc` assumption.

## 14. Reflection magnitude

Method:

```text
vascuquest:spectral:reflection-magnitude-v1
```

The v1 definition is:

```text
R = max(|P_backward|) / max(|P_forward|)
```

after explicit-`Zc` pressure-flow wave separation.

CLI:

```text
vascuquest spectral reflection-magnitude pressure.json flow.json <ZC>
```

Reflection magnitude is method dependent and is not interchangeable with every reflection coefficient definition in the literature.

## 15. Wave intensity

Method:

```text
vascuquest:spectral:wave-intensity-v1
```

For aligned local pressure `P(t)` and velocity `U(t)`:

```text
WI_net = (dP/dt)(dU/dt)
```

Using blood density `ρ` and wave speed `c`, the separated components are:

```text
WI_forward  = (dP/dt + ρ c dU/dt)^2 / (4 ρ c)
WI_backward = -(dP/dt - ρ c dU/dt)^2 / (4 ρ c)
```

Default blood density is 1060 kg/m³ unless explicitly changed.

CLI:

```text
vascuquest spectral wave-intensity pressure.json velocity.json <WAVE_SPEED>
vascuquest spectral wave-intensity pressure.json velocity.json <WAVE_SPEED> --component forward
```

Important warning:

> Wave-intensity rate is derivative-sensitive. Adequate native temporal resolution is required; VascuQuest does not silently upsample low-resolution signals.

## 16. Spectral entropy

`spectral_entropy(...)` summarizes the normalized distribution of spectral energy into a dimensionless scalar under the implemented definition.

CLI:

```text
vascuquest spectral entropy waveform.json
```

It is a signal-complexity descriptor, not a direct clinical disease score.

## 17. Harmonic-energy ratio

`harmonic_energy_ratio(...)` compares explicitly declared low- and high-harmonic energy bands.

CLI:

```text
vascuquest spectral harmonic-energy-ratio waveform.json --low-end 3 --high-start 4 --high-end 10
```

The band definition is part of the method parameters and must be reported in research use.

## 18. STFT

`stft_magnitude(...)` produces a time-frequency magnitude representation under explicit segment/overlap parameters.

CLI:

```text
vascuquest spectral stft waveform.json --nperseg 64
```

The STFT is sensitive to window/segment choices. Time/frequency resolution is a method parameter, not a source-data property.

## 19. Continuous wavelet transform

`cwt_magnitude(...)` provides a continuous-wavelet magnitude representation through the optional research stack (PyWavelets).

The selected wavelet, scales, sampling interval, and edge effects are part of the scientific definition and must be retained/reported.

There is currently no dedicated convenience CLI command for CWT; use the Python API.

## 20. Path-wise harmonic evolution

`path_harmonic_evolution(...)` is designed for analysis of harmonic changes along a source-supported arterial path.

It must preserve actual path-point identity/distance and may not create unstored positions by silent interpolation.

This method is particularly useful with qualified HEMOSPACE dense-path access.

## 21. Individual and cohort use

Spectral functions are fundamentally waveform-level operations. A typical cohort workflow is:

```text
subject waveform(s)
    ↓
subject spectral descriptor
    ↓ preserve canonical ID
cohort vector of descriptors
    ↓
vascuquest.stats
```

Do not treat the many frequency bins of one subject as independent subjects.

## 22. Healthy/disease studies

For a matched Virtual Disease cohort, spectral descriptors can be calculated separately for healthy and modelled disease waveforms and then compared by canonical identity.

Example research endpoint:

> paired change in carotid pressure-flow impedance harmonic magnitude under an identical modelled stenosis

This remains a mechanistic in-silico endpoint, not a clinical treatment outcome.

## 23. Reproducibility requirements

A reported spectral result should identify, as applicable:

- input quantity and vascular location;
- subject/cohort identity;
- native sampling interval;
- detrending/DC convention;
- FFT normalization;
- number/range of harmonics;
- Welch/STFT segment parameters;
- denominator threshold;
- supplied `Zc`;
- supplied wave speed and density;
- wavelet/scales;
- VascuQuest method ID/version.

## 24. Optional dependencies

Install the research stack for SciPy/PyWavelets-based methods:

```text
pip install "vascuquest[research]"
```

A missing dependency causes explicit capability failure; VascuQuest does not silently substitute a different spectral method.

## 25. Non-claims

The spectral layer does not claim:

- causal physiology from coherence/transfer alone;
- a unique universal reflection coefficient;
- direct material-property measurement from characteristic impedance;
- clinical disease diagnosis from spectral entropy or harmonic ratios;
- clinically measured PWV from wave-separation assumptions;
- clinical validation of disease-state spectral responses;
- hidden resampling as a valid substitute for inadequate sampling.
