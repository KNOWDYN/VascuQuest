"""Time-frequency and path-wise spectral analyses."""
from __future__ import annotations
from collections.abc import Sequence
import numpy as np
from vascuquest.analysis import ensure_same_subject, make_result, time_values
from vascuquest.analysis.core import require_optional_dependency
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.result import Coordinate, ScientificResult, Waveform
from vascuquest.errors import AdmissibilityError
from ._shared import _WAVE_CITATIONS, _uniform_signal
from .fourier import harmonic_amplitude

def stft_magnitude(waveform: Waveform, *, nperseg: int = 64, noverlap: int | None = None) -> ScientificResult:
    signal=require_optional_dependency("scipy.signal","research"); _,y,dt=_uniform_signal(waveform); nperseg=min(int(nperseg),y.size)
    if nperseg<4: raise ValueError("nperseg must permit at least four samples")
    overlap=nperseg//2 if noverlap is None else int(noverlap)
    if not 0<=overlap<nperseg: raise ValueError("noverlap must satisfy 0 <= noverlap < nperseg")
    f,tt,z=signal.stft(y,fs=1.0/dt,nperseg=nperseg,noverlap=overlap,boundary=None,padded=False)
    return make_result(waveform,canonical_name=f"spectral.stft_magnitude.{waveform.quantity.canonical_name}",label=f"STFT magnitude: {waveform.quantity.label}",description="Short-time Fourier transform magnitude with explicit segment and overlap settings.",values=np.abs(z),method_id="vascuquest:spectral:stft-v1",parameters={"nperseg":nperseg,"noverlap":overlap,"boundary":None,"padded":False},evidence=EvidenceClass.DERIVED,canonical_unit=waveform.canonical_unit,physical_dimension=waveform.physical_dimension,value_kind="matrix",dimensions=("frequency","time"),coordinates=(Coordinate("frequency",np.asarray(f),"Hz"),Coordinate("time",np.asarray(tt)+time_values(waveform)[0],waveform.time_coordinate.unit)),citations=_WAVE_CITATIONS)

def cwt_magnitude(waveform: Waveform, *, scales: Sequence[float], wavelet: str = "morl") -> ScientificResult:
    pywt=require_optional_dependency("pywt","research"); t,y,dt=_uniform_signal(waveform); scale_array=np.asarray(tuple(scales),dtype=float)
    if scale_array.ndim!=1 or scale_array.size==0 or np.any(scale_array<=0) or not np.all(np.isfinite(scale_array)): raise ValueError("scales must be a non-empty finite positive sequence")
    coeff,frequencies=pywt.cwt(y,scale_array,wavelet,sampling_period=dt)
    return make_result(waveform,canonical_name=f"spectral.cwt_magnitude.{waveform.quantity.canonical_name}",label=f"Continuous-wavelet magnitude: {waveform.quantity.label}",description="Continuous wavelet-transform magnitude with explicit wavelet and scales.",values=np.abs(coeff),method_id="vascuquest:spectral:cwt-v1",parameters={"wavelet":wavelet,"scales":scale_array.tolist()},evidence=EvidenceClass.DERIVED,canonical_unit=waveform.canonical_unit,physical_dimension=waveform.physical_dimension,value_kind="matrix",dimensions=("frequency","time"),coordinates=(Coordinate("frequency",np.asarray(frequencies),"Hz"),Coordinate("time",t,waveform.time_coordinate.unit)),citations=_WAVE_CITATIONS,warnings=("Wavelet edge effects remain present near the beginning and end of the finite waveform.",))

def path_harmonic_evolution(waveforms: Sequence[Waveform], distances_m: Sequence[float], *, harmonic: int = 1) -> ScientificResult:
    waves=tuple(waveforms)
    if not waves: raise ValueError("at least one path waveform is required")
    distances=np.asarray(tuple(distances_m),dtype=float)
    if distances.ndim!=1 or distances.size!=len(waves) or not np.all(np.isfinite(distances)): raise ValueError("distances_m must provide one finite distance per waveform")
    if np.any(np.diff(distances)<0): raise ValueError("distances_m must be non-decreasing")
    ensure_same_subject(*waves); first_quantity=waves[0].quantity.canonical_name; first_unit=waves[0].canonical_unit
    if any(w.quantity.canonical_name!=first_quantity or w.canonical_unit!=first_unit for w in waves[1:]): raise AdmissibilityError("path harmonic evolution requires the same quantity and unit at every path position")
    if harmonic<1: raise ValueError("harmonic must be positive")
    amplitudes=[]
    for wave in waves:
        result=harmonic_amplitude(wave,n_harmonics=harmonic)
        if np.asarray(result.values).size<harmonic: raise AdmissibilityError("requested harmonic is unavailable for one or more path waveforms")
        amplitudes.append(float(np.asarray(result.values)[harmonic-1]))
    return make_result(waves[0],canonical_name=f"spectral.path_harmonic_{harmonic}.{waves[0].quantity.canonical_name}",label=f"Path harmonic {harmonic} evolution",description="Spatial evolution of one waveform harmonic amplitude across explicitly supplied path positions.",values=np.asarray(amplitudes),method_id="vascuquest:spectral:path-harmonic-v1",inputs=waves,parameters={"harmonic":harmonic,"distances_m":distances.tolist()},evidence=EvidenceClass.DERIVED,canonical_unit=waves[0].canonical_unit,physical_dimension=waves[0].physical_dimension,value_kind="series",dimensions=("path_distance",),coordinates=(Coordinate("path_distance",distances,"m"),),location=None,citations=_WAVE_CITATIONS)
