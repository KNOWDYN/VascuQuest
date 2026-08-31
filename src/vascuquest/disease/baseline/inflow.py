"""Reconstruct the exact healthy aortic inflow from canonical PWDB source waves."""

from __future__ import annotations

import numpy as np

from vascuquest.api import DatasetSession
from vascuquest.domain.location import MeasurementSite
from vascuquest.domain.result import Waveform
from vascuquest.errors import AdmissibilityError

from .model import InflowWaveform


def _active_samples(waveform: Waveform) -> np.ndarray:
    values = np.asarray(waveform.values, dtype=float)
    missing = np.zeros(values.shape, dtype=bool) if waveform.missing_mask is None else np.asarray(waveform.missing_mask, dtype=bool)
    padding = np.zeros(values.shape, dtype=bool) if waveform.padding_mask is None else np.asarray(waveform.padding_mask, dtype=bool)
    if missing.shape != values.shape or padding.shape != values.shape:
        raise AdmissibilityError("PWDB waveform masks do not align with source samples")
    active = ~(missing | padding)
    if not np.any(active):
        raise AdmissibilityError("PWDB aortic-root waveform contains no active source samples")
    if np.any(missing & ~padding):
        raise AdmissibilityError("PWDB aortic-root waveform contains internal missing samples")
    return active


def source_aortic_inflow(session: DatasetSession, subject_id: str) -> InflowWaveform:
    """Return Q=U*A at AorticRoot as the preserved healthy cardiac input.

    None of the four frozen v1 arterial disease presets alters cardiac inflow.
    Using the exact source-derived aortic-root Q therefore avoids inventing an
    inlet-wave generator during healthy reconstruction and preserves the
    selected subject's original cardiac forcing.
    """

    if not isinstance(session, DatasetSession):
        raise TypeError("session must be a DatasetSession")
    if not isinstance(subject_id, str) or not subject_id.strip():
        raise ValueError("subject_id must be a non-empty string")
    site = MeasurementSite("AorticRoot")
    velocity = session.waveform("flow_velocity", subject=subject_id, location=site)
    area = session.waveform("luminal_area", subject=subject_id, location=site)
    v_active = _active_samples(velocity)
    a_active = _active_samples(area)
    if not np.array_equal(v_active, a_active):
        raise AdmissibilityError("aortic-root U and A source masks are not aligned")
    v_time = np.asarray(velocity.time_coordinate.values, dtype=float)
    a_time = np.asarray(area.time_coordinate.values, dtype=float)
    if v_time.shape != a_time.shape or not np.allclose(v_time, a_time, rtol=0.0, atol=1e-12):
        raise AdmissibilityError("aortic-root U and A time coordinates are not aligned")
    active = v_active
    q = np.asarray(velocity.values, dtype=float)[active] * np.asarray(area.values, dtype=float)[active]
    time = v_time[active]
    return InflowWaveform(
        time_s=time,
        flow_m3_per_s=q,
        source_identity="PWDB:AorticRoot:Q=U*A",
    )


__all__ = ["source_aortic_inflow"]
