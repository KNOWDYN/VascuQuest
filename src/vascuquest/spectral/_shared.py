from __future__ import annotations
import numpy as np
from vascuquest.analysis import time_values, waveform_values
from vascuquest.domain.result import Waveform
from vascuquest.errors import AdmissibilityError

_WAVE_CITATIONS=("DOI:10.1161/HYP.0000000000000033","PMID:25138163","DOI:10.1093/eurheartj/ehy346")

def _uniform_signal(waveform: Waveform) -> tuple[np.ndarray, np.ndarray, float]:
    t = time_values(waveform)
    y = waveform_values(waveform)
    dt_values = np.diff(t)
    dt = float(np.median(dt_values))
    if dt <= 0 or not np.allclose(dt_values, dt, rtol=1e-6, atol=max(1e-12, abs(dt) * 1e-9)):
        raise AdmissibilityError("spectral analysis requires a uniformly sampled waveform; no silent resampling is performed")
    return t, y, dt

def _rfft_coefficients(waveform: Waveform, *, demean: bool = True) -> tuple[np.ndarray, np.ndarray, float]:
    _, y, dt = _uniform_signal(waveform)
    signal = y - np.mean(y) if demean else y
    coeff = np.fft.rfft(signal)
    freq = np.fft.rfftfreq(signal.size, d=dt)
    return freq, coeff, dt
