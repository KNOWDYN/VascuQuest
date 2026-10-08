"""Fourier, cross-spectral and transfer analyses."""
from __future__ import annotations
import numpy as np
from vascuquest.analysis import ensure_aligned_waveforms, make_result, waveform_values
from vascuquest.analysis.core import require_optional_dependency
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.result import Coordinate, ScientificResult, Waveform
from vascuquest.errors import AdmissibilityError
from ._shared import _WAVE_CITATIONS, _rfft_coefficients, _uniform_signal

def harmonic_amplitude(waveform: Waveform, *, n_harmonics: int = 10, include_dc: bool = False) -> ScientificResult:
    if n_harmonics < 1: raise ValueError("n_harmonics must be positive")
    freq, coeff, _ = _rfft_coefficients(waveform, demean=False); n = waveform_values(waveform).size
    amp = np.abs(coeff) / n
    if amp.size > 1: amp[1:-1 if n % 2 == 0 else None] *= 2.0
    start = 0 if include_dc else 1; stop = min(amp.size, n_harmonics + 1); harmonic = np.arange(start, stop, dtype=int)
    return make_result(waveform, canonical_name=f"spectral.harmonic_amplitude.{waveform.quantity.canonical_name}", label=f"Harmonic amplitude: {waveform.quantity.label}", description="One-sided DFT harmonic amplitudes on the native uniformly sampled cycle.", values=amp[start:stop], method_id="vascuquest:spectral:harmonic-amplitude-v1", parameters={"n_harmonics":n_harmonics,"include_dc":include_dc}, evidence=EvidenceClass.DERIVED, canonical_unit=waveform.canonical_unit, physical_dimension=waveform.physical_dimension, value_kind="series", dimensions=("harmonic",), coordinates=(Coordinate("harmonic",harmonic,"1"),Coordinate("frequency",freq[start:stop],"Hz")), citations=_WAVE_CITATIONS)

def harmonic_phase(waveform: Waveform, *, n_harmonics: int = 10) -> ScientificResult:
    if n_harmonics < 1: raise ValueError("n_harmonics must be positive")
    freq, coeff, _ = _rfft_coefficients(waveform, demean=True); stop=min(coeff.size,n_harmonics+1); harmonic=np.arange(1,stop,dtype=int)
    return make_result(waveform, canonical_name=f"spectral.harmonic_phase.{waveform.quantity.canonical_name}", label=f"Harmonic phase: {waveform.quantity.label}", description="DFT harmonic phase referenced to the first native sample after mean removal.", values=np.angle(coeff[1:stop]), method_id="vascuquest:spectral:harmonic-phase-v1", parameters={"n_harmonics":n_harmonics,"phase_reference":"first_sample_after_mean_removal"}, evidence=EvidenceClass.DERIVED, canonical_unit="rad", physical_dimension="angle", value_kind="series", dimensions=("harmonic",), coordinates=(Coordinate("harmonic",harmonic,"1"),Coordinate("frequency",freq[1:stop],"Hz")), citations=_WAVE_CITATIONS)

def power_spectral_density(waveform: Waveform, *, detrend: str = "constant") -> ScientificResult:
    signal=require_optional_dependency("scipy.signal","research"); _,y,dt=_uniform_signal(waveform); f,psd=signal.periodogram(y,fs=1.0/dt,detrend=detrend,scaling="density",return_onesided=True); unit=None if waveform.canonical_unit is None else f"({waveform.canonical_unit})^2/Hz"
    return make_result(waveform, canonical_name=f"spectral.psd.{waveform.quantity.canonical_name}", label=f"Power spectral density: {waveform.quantity.label}", description="One-sided periodogram power spectral density on the native uniformly sampled waveform.", values=np.asarray(psd), method_id="vascuquest:spectral:periodogram-v1", parameters={"detrend":detrend,"scaling":"density"}, evidence=EvidenceClass.DERIVED, canonical_unit=unit, physical_dimension=None, value_kind="series", dimensions=("frequency",), coordinates=(Coordinate("frequency",np.asarray(f),"Hz"),), citations=_WAVE_CITATIONS)

def coherence(x: Waveform, y: Waveform, *, nperseg: int | None = None) -> ScientificResult:
    ensure_aligned_waveforms(x,y,require_same_location=False); signal=require_optional_dependency("scipy.signal","research"); _,xv,dt=_uniform_signal(x); yv=waveform_values(y); nseg=min(xv.size,nperseg or min(256,xv.size)); f,coh=signal.coherence(xv,yv,fs=1.0/dt,nperseg=nseg)
    return make_result(x, canonical_name=f"spectral.coherence.{x.quantity.canonical_name}.{y.quantity.canonical_name}", label="Magnitude-squared coherence", description="Magnitude-squared coherence between aligned waveforms for the same virtual subject; locations may differ.", values=np.asarray(coh), method_id="vascuquest:spectral:coherence-v1", inputs=(x,y), parameters={"nperseg":nseg}, evidence=EvidenceClass.DERIVED, canonical_unit="1", physical_dimension="dimensionless", value_kind="series", dimensions=("frequency",), coordinates=(Coordinate("frequency",np.asarray(f),"Hz"),), citations=_WAVE_CITATIONS, location=None)

def cross_spectral_density(x: Waveform, y: Waveform, *, nperseg: int | None = None) -> tuple[ScientificResult, ScientificResult]:
    ensure_aligned_waveforms(x,y,require_same_location=False); signal=require_optional_dependency("scipy.signal","research"); _,xv,dt=_uniform_signal(x); _,yv,_=_uniform_signal(y); nseg=min(xv.size,nperseg or min(256,xv.size)); f,pxy=signal.csd(xv,yv,fs=1.0/dt,nperseg=nseg,detrend="constant",scaling="density")
    common=dict(inputs=(x,y),parameters={"nperseg":nseg,"scaling":"density"},evidence=EvidenceClass.DERIVED,value_kind="series",dimensions=("frequency",),coordinates=(Coordinate("frequency",np.asarray(f),"Hz"),),citations=_WAVE_CITATIONS,subject=x.subject,cohort=x.cohort,location=None)
    magnitude=make_result(x,canonical_name=f"spectral.csd_magnitude.{x.quantity.canonical_name}.{y.quantity.canonical_name}",label="Cross-spectral density magnitude",description="Magnitude of the cross-spectral density between aligned VascuQuest waveforms.",values=np.abs(pxy),method_id="vascuquest:spectral:csd-v1",canonical_unit=None,physical_dimension=None,**common)
    phase=make_result(x,canonical_name=f"spectral.csd_phase.{x.quantity.canonical_name}.{y.quantity.canonical_name}",label="Cross-spectral density phase",description="Phase of the cross-spectral density between aligned VascuQuest waveforms.",values=np.angle(pxy),method_id="vascuquest:spectral:csd-v1",canonical_unit="rad",physical_dimension="angle",**common)
    return magnitude,phase

def transfer_function(input_waveform: Waveform, output_waveform: Waveform, *, nperseg: int | None = None, min_input_fraction: float = 1e-12) -> tuple[ScientificResult, ScientificResult]:
    ensure_aligned_waveforms(input_waveform,output_waveform,require_same_location=False); signal=require_optional_dependency("scipy.signal","research"); _,x,dt=_uniform_signal(input_waveform); _,y,_=_uniform_signal(output_waveform); nseg=min(x.size,nperseg or min(256,x.size)); f,sxx=signal.welch(x,fs=1.0/dt,nperseg=nseg,detrend="constant",scaling="density"); f2,sxy=signal.csd(x,y,fs=1.0/dt,nperseg=nseg,detrend="constant",scaling="density")
    if not np.allclose(f,f2,rtol=0.0,atol=1e-12): raise RuntimeError("internal transfer-function frequency grids are inconsistent")
    threshold=max(float(np.max(np.abs(sxx)))*min_input_fraction,np.finfo(float).tiny); valid=np.abs(sxx)>threshold; h=np.full(sxy.shape,np.nan+1j*np.nan,dtype=complex); h[valid]=sxy[valid]/sxx[valid]; warnings=() if np.all(valid) else ("One or more transfer-function frequencies were undefined because input power was below threshold.",)
    common=dict(inputs=(input_waveform,output_waveform),parameters={"nperseg":nseg,"min_input_fraction":min_input_fraction,"estimator":"H1=Sxy/Sxx"},evidence=EvidenceClass.DERIVED,value_kind="series",dimensions=("frequency",),coordinates=(Coordinate("frequency",np.asarray(f),"Hz"),),citations=_WAVE_CITATIONS,warnings=warnings,subject=input_waveform.subject,cohort=input_waveform.cohort,location=None)
    mag=make_result(input_waveform,canonical_name="spectral.transfer_magnitude",label="Transfer-function magnitude",description="Magnitude of the H1 frequency-response estimate Sxy/Sxx.",values=np.abs(h),method_id="vascuquest:spectral:transfer-h1-v1",canonical_unit=None,physical_dimension=None,**common)
    phase=make_result(input_waveform,canonical_name="spectral.transfer_phase",label="Transfer-function phase",description="Phase of the H1 frequency-response estimate Sxy/Sxx.",values=np.angle(h),method_id="vascuquest:spectral:transfer-h1-v1",canonical_unit="rad",physical_dimension="angle",**common)
    return mag,phase

def spectral_entropy(waveform: Waveform) -> ScientificResult:
    psd=power_spectral_density(waveform); p=np.asarray(psd.values,dtype=float); total=float(np.sum(p))
    if total<=0: raise AdmissibilityError("spectral entropy requires non-zero spectral power")
    prob=p/total; prob=prob[prob>0]; entropy=float(-np.sum(prob*np.log(prob))/np.log(max(2,p.size)))
    return make_result(waveform,canonical_name=f"spectral.entropy.{waveform.quantity.canonical_name}",label="Normalized spectral entropy",description="Shannon entropy of the normalized one-sided periodogram, normalized by log(number of frequency bins).",values=entropy,method_id="vascuquest:spectral:entropy-v1",inputs=(waveform,),evidence=EvidenceClass.DERIVED,canonical_unit="1",physical_dimension="dimensionless",value_kind="scalar",citations=_WAVE_CITATIONS)

def harmonic_energy_ratio(waveform: Waveform, *, low_end: int = 3, high_start: int = 4, high_end: int = 10) -> ScientificResult:
    if not (1<=low_end<high_start<=high_end): raise ValueError("harmonic bands must satisfy 1 <= low_end < high_start <= high_end")
    amp=harmonic_amplitude(waveform,n_harmonics=high_end); a=np.asarray(amp.values,dtype=float)
    if a.size<high_end: raise AdmissibilityError("waveform does not support the requested harmonic-energy bands")
    low=float(np.sum(a[:low_end]**2)); high=float(np.sum(a[high_start-1:high_end]**2))
    if low<=0: raise AdmissibilityError("low-harmonic energy is zero; high/low ratio is undefined")
    return make_result(waveform,canonical_name=f"spectral.harmonic_energy_ratio.{waveform.quantity.canonical_name}",label="High-to-low harmonic energy ratio",description="Explicit high-band to low-band squared-harmonic-amplitude ratio.",values=high/low,method_id="vascuquest:spectral:harmonic-energy-ratio-v1",inputs=(waveform,),parameters={"low_band":[1,low_end],"high_band":[high_start,high_end]},evidence=EvidenceClass.DERIVED,canonical_unit="1",physical_dimension="dimensionless",value_kind="scalar",citations=_WAVE_CITATIONS)
